"""
Agent 认知循环 — perceive → decide → act → observe。

=== 这个文件是整个 Agent 的核心 ===

AgentLoop 就是 Agent 的"大脑引擎"。它管理着 ReAct 循环：

    用户输入
        ↓
    ┌─→ [Decide] LLM 推理：输出 Thought + Action 或 Final Answer
    │     ↓
    │   如果是 Final Answer → 返回结果，循环结束
    │     ↓
    │   [Act] 解析 Action，调用对应工具
    │     ↓
    │   [Observe] 把工具结果作为 Observation 回传给 LLM
    └──← 重复

=== 为什么有 max_iterations？===
如果 LLM 一直不输出 Final Answer，循环就停不下来。
max_iterations 是安全阀，超过就报错停止。
"""

from __future__ import annotations

# re 是正则表达式模块，用于从 LLM 输出中提取 Action 和 Final Answer
import re

# dataclass 和 field 用于简化数据类的定义
from dataclasses import dataclass, field

# 导入 LLM 客户端基类
from src.llm.base_client import BaseLLMClient

# 导入记忆管理器
from src.memory.manager import MemoryManager

# 导入工具基类
from src.tools.base_tool import BaseTool

# 导入自定义异常
# MaxIterationsError: 超过最大迭代次数时抛出
from src.utils.exceptions import MaxIterationsError

# 导入提示词模板（人设、few-shot、任务包装、格式纠错都在 src/prompts/*.md）
from src.prompts.loader import build_chat_messages, load_prompt

# 导入日志
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
        # ===== 第 1 步：感知（Perceive）=====
        # 构建带 role 的消息列表：
        # system（system.md + examples.md）+ 历史 + 当前用户输入（task.md）
        # 由 ChatPromptTemplate.from_messages 组装，再转成 OpenAI dict
        tool_desc = "\n".join(
            f"  - {t.name}: {t.description}" for t in self.tools
        )
        messages = build_chat_messages(
            tool_descriptions=tool_desc,
            history=self._load_history(),
            user_input=user_input,
        )

        # ===== 第 2 步：循环（Decide → Act → Observe）=====
        # range(1, self.max_iterations + 1) 生成 1, 2, 3, ..., max_iterations
        for i in range(1, self.max_iterations + 1):
            self._iteration_count = i  # 记录当前迭代轮数
            logger.debug("Iteration %d/%d", i, self.max_iterations)

            # ----- 决策（Decide）-----
            # 把所有消息发给 LLM，让它"思考"下一步该做什么
            # LLM 会输出两种格式之一：
            #   格式1: "Thought: ...\nAction[tool_name](args)"  → 需要调用工具
            #   格式2: "Thought: ...\nFinal Answer: ..."           → 直接给答案
            response = await self.llm_client.chat(messages)

            # 把 LLM 的回复加入消息列表（这样下一轮 LLM 能看到自己上一轮说了什么）
            messages.append({"role": "assistant", "content": response})

            # 检查 LLM 是否输出了 Final Answer
            final_answer = self._extract_final_answer(response)
            if final_answer is not None:
                # LLM 给出了最终答案，保存对话到记忆，然后返回
                self._save_history(user_input, final_answer)
                logger.info("Final answer at iteration %d", i)
                return final_answer

            # ----- 执行（Act）-----
            # 尝试从 LLM 输出中解析出 Action[tool_name](args)
            action = self._parse_action(response)
            if action is None:
                # 没有 Action。可能是：
                # 1) 模型直接用自然语言答了（常见于「你叫什么」这类闲聊）
                # 2) 只写了 Thought，ReAct 格式不完整
                #
                # 以前这里只注入 "Please use the format: Action[tool_name](args)"，
                # 模型会把这条 user 消息当成新问题，开始解释格式，丢掉原问题。
                if self._is_plain_reply(response):
                    answer = response.strip()
                    self._save_history(user_input, answer)
                    logger.info("Plain reply accepted as final answer at iteration %d", i)
                    return answer

                messages.append({
                    "role": "user",
                    "content": load_prompt("retry.md"),
                })
                continue  # 跳过本轮，进入下一轮循环

            # 解析成功，执行工具调用
            # action 是一个元组 (tool_name, args)，例如 ("calculator", "15 * 23")
            observation = await self._execute_action(action)

            # ----- 观察（Observe）-----
            # 把工具执行结果作为 Observation 传回给 LLM
            # LLM 看到 Observation 后，会在下一轮决定是继续调用工具还是给出答案
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}",
            })

        # 循环结束还没返回，说明超过了最大迭代次数
        # 这是一个安全机制，防止 Agent 陷入无限循环
        raise MaxIterationsError(
            f"Agent exceeded max iterations ({self.max_iterations})"
        )

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
