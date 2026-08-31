"""
Agent 认知循环 — perceive → decide → act → observe。

=== 这个文件是整个 Agent 的核心 ===

AgentLoop 就是 Agent 的"大脑引擎"。ReAct 规则没变，但转圈改由
LangGraph 的 StateGraph 驱动：一份 AgentState 在节点之间传递。

    用户输入
        ↓
    [perceive] 拼 messages 写入 State
        ↓
    ┌─→ [decide] 读 State["messages"]，调 LLM，只返回增量
    │     ↓
    │   final_answer 有值 → END
    │     ↓
    │   [act] 调工具，把 Observation 追加进 State["messages"]
    │     ↓
    │   或 [retry] 追加格式纠错
    └──← 回到 decide

节点不要改 State 里的列表原地 append。正确做法是：
    return {"messages": [新消息]}
由 append_messages 这个 reducer 合并。

=== 为什么有 max_iterations？===
如果 LLM 一直不输出 Final Answer，循环就停不下来。
max_iterations 是安全阀，超过就报错停止。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from src.core.state import AgentState
from src.llm.base_client import BaseLLMClient
from src.memory.manager import MemoryManager
from src.prompts.loader import build_chat_messages, load_prompt
from src.tools.base_tool import BaseTool
from src.utils.exceptions import MaxIterationsError
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AgentLoop:
    """
    ReAct 认知循环核心。

    管理 Thought → Action → Observation 循环，
    直到 LLM 输出 Final Answer 或达到最大迭代次数。

    === 工作流程详解 ===

    假设用户问 "15 * 23 等于多少"：

    第 1 轮循环：
        messages = [系统提示词, 用户问题]
        → LLM 输出: "Thought: 需要计算\nAction[calculator](15 * 23)"
        → 解析出 Action: 调用计算器工具，参数 "15 * 23"
        → 工具返回: "15 * 23 = 345"
        → 把结果作为 Observation 加入 messages

    第 2 轮循环：
        messages = [系统提示词, 用户问题, LLM回复, Observation]
        → LLM 输出: "Thought: 算出来了\nFinal Answer: 15 * 23 = 345"
        → 检测到 Final Answer，返回 "15 * 23 = 345"

    Attributes:
        llm_client: LLM 客户端，用于调用大模型 API。
        tools: 可用工具列表，Agent 通过这些工具"动手"。
        memory: 记忆管理器，用于存储和加载对话历史。
        max_iterations: 最大循环次数，防止死循环。
    """

    llm_client: BaseLLMClient
    tools: list[BaseTool] = field(default_factory=list)
    memory: MemoryManager | None = None
    max_iterations: int = 10

    # 记录上次 execute() 实际执行了多少轮循环
    # 供 API 层查询并返回给调用方
    _iteration_count: int = field(default=0, repr=False)
    # 编译好的 StateGraph。节点闭包里用 self，所以工具/LLM 变了仍读得到
    _graph: Any = field(default=None, repr=False, init=False)

    def __post_init__(self) -> None:
        self._graph = self._compile_graph()

    async def execute(self, user_input: str) -> str:
        """
        执行完整的 ReAct 循环。

        这是整个 Agent 的"主循环"，是理解 Agent 工作原理的关键。

        Args:
            user_input: 用户输入文本。

        Returns:
            Agent 最终回复。

        Raises:
            MaxIterationsError: 超过最大迭代次数。
        """
        # 图的起点。nodes 只返回增量，messages 靠 reducer 越攒越长。
        initial: AgentState = {
            "messages": [],
            "user_input": user_input,
            "iteration": 0,
            "last_response": "",
            "final_answer": None,
        }
        # recursion_limit 是图跳数上限，不是 LLM 轮数。
        # 一轮 ReAct 大约 perceive + decide + act，所以比 max_iterations 留几倍余量。
        result = await self._graph.ainvoke(
            initial,
            {"recursion_limit": self.max_iterations * 4 + 8},
        )
        self._iteration_count = result["iteration"]
        answer = result.get("final_answer")
        if answer:
            self._save_history(user_input, answer)
            logger.info("Final answer at iteration %d", result["iteration"])
            return answer
        raise MaxIterationsError(
            f"Agent exceeded max iterations ({self.max_iterations})"
        )

    def _compile_graph(self) -> Any:
        """
        把 ReAct 编成 StateGraph。

        边：START → perceive → decide ⇄ act/retry → END
        条件边读的是 State，不是节点返回值。
        """
        graph = StateGraph(AgentState)
        graph.add_node("perceive", self._node_perceive)
        graph.add_node("decide", self._node_decide)
        graph.add_node("act", self._node_act)
        graph.add_node("retry", self._node_retry)
        graph.add_edge(START, "perceive")
        graph.add_edge("perceive", "decide")
        graph.add_conditional_edges(
            "decide",
            self._route_after_decide,
            {"act": "act", "retry": "retry", "end": END},
        )
        graph.add_edge("act", "decide")
        graph.add_edge("retry", "decide")
        return graph.compile()

    def _node_perceive(self, state: AgentState) -> dict:
        """感知：拼第一份 messages。reducer 会把它接到空列表后面。"""
        tool_desc = "\n".join(
            f"  - {t.name}: {t.description}" for t in self.tools
        )
        messages = build_chat_messages(
            tool_descriptions=tool_desc,
            history=self._load_history(),
            user_input=state["user_input"],
        )
        return {"messages": messages}

    async def _node_decide(self, state: AgentState) -> dict:
        """决策：调 LLM。只返回新增的 assistant 消息，不要把整份 messages 塞回去。"""
        if state["iteration"] >= self.max_iterations:
            return {}

        iteration = state["iteration"] + 1
        logger.debug("Iteration %d/%d", iteration, self.max_iterations)
        response = await self.llm_client.chat(state["messages"])

        update: dict = {
            "messages": [{"role": "assistant", "content": response}],
            "last_response": response,
            "iteration": iteration,
        }
        final_answer = self._extract_final_answer(response)
        if final_answer is not None:
            update["final_answer"] = final_answer
            return update
        if self._parse_action(response) is None and self._is_plain_reply(response):
            update["final_answer"] = response.strip()
        return update

    async def _node_act(self, state: AgentState) -> dict:
        """行动+观察：跑工具，把 Observation 追加进 messages。"""
        action = self._parse_action(state["last_response"])
        if action is None:
            return {"last_response": ""}
        observation = await self._execute_action(action)
        return {
            "messages": [{"role": "user", "content": f"Observation: {observation}"}],
            "last_response": "",
        }

    def _node_retry(self, state: AgentState) -> dict:
        """格式不完整：追加纠错提示，下一轮 decide 继续答原来的问题。"""
        return {"messages": [{"role": "user", "content": load_prompt("retry.md")}]}

    def _route_after_decide(self, state: AgentState) -> Literal["act", "retry", "end"]:
        """根据 State 决定下一跳。这就是 LangGraph 的条件边。"""
        if state.get("final_answer"):
            return "end"
        if self._parse_action(state["last_response"]):
            return "act"
        if state["iteration"] >= self.max_iterations:
            return "end"
        return "retry"

    def _build_system_prompt(self) -> str:
        """
        构建 system prompt，注入工具描述。

        system prompt 是发给 LLM 的第一条消息，告诉它：
        1. 你是一个 ReAct Agent
        2. 你有哪些工具可以用
        3. 你应该按什么格式输出

        Returns:
            组装好的系统提示词字符串。
        """
        # 把每个工具的名称和描述拼成一段文字
        # 例如："- calculator: Perform mathematical calculations..."
        tool_desc = "\n".join(
            f"  - {t.name}: {t.description}" for t in self.tools
        )
        # 人设和 few-shot 都在 markdown 模板里，由 ChatPromptTemplate 渲染
        messages = build_chat_messages(tool_desc, history=[], user_input="")
        return messages[0]["content"]

    def _load_history(self) -> list[dict]:
        """
        从记忆中加载对话历史。

        如果没有配置记忆系统，返回空列表（不影响基本运行）。

        Returns:
            消息列表，格式同 OpenAI messages 格式。
        """
        if self.memory is None:
            return []
        return self.memory.get_recent_history()

    def _save_history(self, user_input: str, answer: str) -> None:
        """
        保存对话到记忆。

        在 Agent 给出最终答案后，把这次对话存入记忆系统，
        下次对话时 LLM 就能看到之前的上下文。

        Args:
            user_input: 用户问了什么。
            answer: Agent 回答了什么。
        """
        if self.memory is None:
            return
        self.memory.add_message("user", user_input)
        self.memory.add_message("assistant", answer)

    @staticmethod
    def _extract_final_answer(response: str) -> str | None:
        """
        从 LLM 输出中提取 Final Answer。

        LLM 输出格式示例：
            "Thought: 算出来了\nFinal Answer: 15 * 23 = 345"

        用正则表达式找到 "Final Answer:" 后面的内容。

        Args:
            response: LLM 的完整输出文本。

        Returns:
            提取到的答案文本，或 None（如果没有 Final Answer）。
        """
        # re.search 在文本中搜索匹配的模式
        # r"Final Answer:\s*(.+)" 意思是：
        #   "Final Answer:" → 字面匹配这几个字
        #   \s*              → 匹配零个或多个空白字符（空格、换行等）
        #   (.+)             → 匹配一个或多个任意字符（捕获到分组里）
        # re.DOTALL 让 . 也能匹配换行符
        match = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL)
        # 如果匹配成功，match.group(1) 返回第一个捕获组的内容
        # .strip() 去除首尾空白
        # 如果没匹配（match is None），返回 None
        return match.group(1).strip() if match else None

    @staticmethod
    def _is_plain_reply(response: str) -> bool:
        """
        判断 LLM 是否在用自然语言直接回答（没有走 ReAct 标记）。

        「你叫什么」这类问题，模型经常不写 Thought/Action/Final Answer，
        直接回「我是 xxx」。这种回复应当原样返回，而不是逼它改成 Action。
        """
        text = response.strip()
        if not text:
            return False
        if re.search(r"(?i)^\s*Thought\s*:", text) or "Action[" in text:
            return False
        return True

    @staticmethod
    def _parse_action(response: str) -> tuple[str, str] | None:
        """
        解析 Action[tool_name](args) 格式。

        LLM 输出格式示例：
            "Thought: 需要计算\nAction[calculator](15 * 23)"

        用正则表达式提取工具名和参数。

        Args:
            response: LLM 的完整输出文本。

        Returns:
            (tool_name, args) 元组，或 None（如果没有 Action）。
        """
        # 正则解释：r"Action\[(\w+)\]\((.+?)\)"
        #   Action\[    → 匹配 "Action[" （[ 是特殊字符，要转义）
        #   (\w+)       → 匹配一个或多个字母/数字/下划线，捕获为工具名
        #   \]\(        → 匹配 "]("
        #   (.+?)       → 非贪婪匹配参数内容（尽可能少匹配）
        #   \)          → 匹配 ")"
        match = re.search(r"Action\[(\w+)\]\((.+?)\)", response, re.DOTALL)
        if not match:
            return None
        # match.group(1) = 工具名, match.group(2) = 参数
        return match.group(1), match.group(2).strip()

    async def _execute_action(self, action: tuple[str, str]) -> str:
        """
        执行工具调用。

        根据解析出的 (tool_name, args)，找到对应的工具并执行。

        Args:
            action: (tool_name, args) 元组。
                    例如 ("calculator", "15 * 23")。

        Returns:
            工具执行结果字符串。
            如果工具不存在或执行失败，返回错误信息（不抛异常，
            而是把错误作为 Observation 让 LLM 看到，它可以调整策略）。
        """
        # 解构元组：tool_name = "calculator", args = "15 * 23"
        tool_name, args = action

        # 在工具列表中查找对应名称的工具
        # next() 返回第一个满足条件的元素，找不到返回 None
        tool = next((t for t in self.tools if t.name == tool_name), None)

        if tool is None:
            # 工具不存在，返回错误信息（不抛异常）
            # 这样 LLM 能看到错误并调整策略（比如改用其他工具）
            return f"Error: Tool '{tool_name}' not found"

        try:
            # 调用工具的 run 方法执行操作
            # await 因为 run 是异步方法
            result = await tool.run(args)
            return str(result)
        except Exception as e:
            # 工具执行失败，记录错误并返回错误信息
            logger.error("Tool '%s' failed: %s", tool_name, e)
            return f"Error: {e}"
