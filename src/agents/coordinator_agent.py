"""
主 Agent（Coordinator）+ 三个子 Agent。

=== 多 Agent 怎么分工？===

    用户
      ↓
    CoordinatorAgent（主：只负责分活，自己不算、不写长文）
      ├── math_agent       算术，内部有计算器
      ├── writer_agent     改写 / 总结 / 通俗解释
      ├── knowledge_agent  查知识库（RAG：retrieve 工具）
      └── general_agent    闲聊、常识问答

主 Agent 的「工具」其实是子 Agent（见 DelegateTool）。
子 Agent 各自再跑一轮自己的 ReAct 循环，把答案交回主 Agent。

=== 例子 ===
用户：15 乘 23 等于多少？再用一句话说人话。

主 Agent 第 1 轮：Action[math_agent](15 * 23)
  └─ 子 Agent 用计算器 → 345
主 Agent 第 2 轮：Action[writer_agent](把 345 说成一句人话)
  └─ 子 Agent → 「15 乘 23 等于 345。」
主 Agent 第 3 轮：Final Answer: ...

用户：年假有几天？
主 Agent：Action[knowledge_agent](年假天数)
  └─ 知识专家 Action[retrieve](年假) → 知识库段落 → Final Answer

=== 和 AgentScope 版的关系 ===
这是 AGENT_BACKEND=handmade 时用的实现。
同一张分工图的官方框架版见 scope_coordinator.py。
"""

from __future__ import annotations

from src.agents.react_agent import ReactAgent
from src.llm.base_client import BaseLLMClient
from src.tools.calculator import CalculatorTool
from src.tools.delegate import DelegateTool
from src.tools.retrieve import RetrieveTool
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 人设（role_prompt）
# 会写进各自的 system prompt。注意：手写循环靠正则解析，
# Thought / Action / Final Answer 这三个英文关键词必须保留。
# ---------------------------------------------------------------------------

MATH_ROLE = (
    "你是数学专家 MathAgent，专门做算术。"
    "必须使用 calculator 工具计算，不要心算或猜测。"
    "看到 Observation 之后，用 Final Answer 给出带数字的结果。"
)

WRITER_ROLE = (
    "你是写作专家 WriterAgent，专门改写、总结、把话讲明白。"
    "你没有工具。必须直接用 Final Answer 作答。"
    "用和任务相同的语言回复。"
)

GENERAL_ROLE = (
    "你是通用专家 GeneralAgent，负责闲聊和常识问答。"
    "你没有工具。必须直接用 Final Answer 作答。"
    "用和用户相同的语言回复。"
)

KNOWLEDGE_ROLE = (
    "你是知识专家 KnowledgeAgent，专门查知识库。"
    "必须使用 retrieve 工具检索，不要凭记忆编造文档内容。"
    "看到 Observation 之后，用 Final Answer 根据检索结果作答。"
    "如果检索说没有相关内容，就如实告诉用户知识库里没有，不要编。"
)

COORD_ROLE = """你是主 Agent（CoordinatorAgent），负责给专家分活，不要自己做专家的工作。

分工：
- 算术、公式、数字计算 → math_agent
- 改写、总结、翻译、通俗解释 → writer_agent
- 问公司制度、项目说明、文档、知识库里的事实 → knowledge_agent
- 闲聊、常识、其他问题 → general_agent

可以连续调用多个子 Agent（例如先 knowledge_agent 再 writer_agent）。
拿到足够的 Observation 之后，用 Final Answer 回答用户。
除非用户问内部原理，否则不要提及工具名。"""


class CoordinatorAgent(ReactAgent):
    """
    主 Agent：把用户任务分给子 Agent。

    继承 ReactAgent：外壳（组装 LLM / 工具 / 记忆）和循环都复用，
    这里只负责「创建四个专家，再把他们包装成工具交给主管」。

    HTTP / 命令行在 AGENT_BACKEND=handmade 时创建的就是这个类。
    """

    def __init__(
        self,
        name: str = "CoordinatorAgent",
        *,
        session_id: str | None = None,
        llm_client: BaseLLMClient | None = None,
        math_llm: BaseLLMClient | None = None,
        writer_llm: BaseLLMClient | None = None,
        general_llm: BaseLLMClient | None = None,
        knowledge_llm: BaseLLMClient | None = None,
        max_iterations: int = 10,
    ) -> None:
        """
        Args:
            name: 主 Agent 名字，出现在日志和 /chat 的 agent 字段。
            session_id: 会话 ID。只主 Agent 用来记对话；子 Agent 不记。
            llm_client: 主管自己的 LLM。测试时可注入假客户端。
            math_llm / writer_llm / general_llm / knowledge_llm: 四个专家各自的 LLM。
                不传则每个 ReactAgent 自己用 LLMFactory 建一个真实客户端。
            max_iterations: 主、子循环各自最多转几圈（保险丝）。
        """
        # use_memory=False：专家一次任务结束就忘，避免把「15*23」写进主管的会话历史
        math_agent = ReactAgent(
            name="MathAgent",
            llm_client=math_llm,
            tools=[CalculatorTool()],
            use_memory=False,
            role_prompt=MATH_ROLE,
            max_iterations=max_iterations,
        )
        # tools=[] 表示「没有工具」，不要传 None（None 会给默认计算器）
        writer_agent = ReactAgent(
            name="WriterAgent",
            llm_client=writer_llm,
            tools=[],
            use_memory=False,
            role_prompt=WRITER_ROLE,
            max_iterations=max_iterations,
        )
        general_agent = ReactAgent(
            name="GeneralAgent",
            llm_client=general_llm,
            tools=[],
            use_memory=False,
            role_prompt=GENERAL_ROLE,
            max_iterations=max_iterations,
        )
        knowledge_agent = ReactAgent(
            name="KnowledgeAgent",
            llm_client=knowledge_llm,
            tools=[RetrieveTool()],
            use_memory=False,
            role_prompt=KNOWLEDGE_ROLE,
            max_iterations=max_iterations,
        )

        # 给日志 /health 用：主 Agent 能调度谁
        self.sub_agents = {
            "math_agent": math_agent,
            "writer_agent": writer_agent,
            "general_agent": general_agent,
            "knowledge_agent": knowledge_agent,
        }

        # 主管自己：有记忆、工具是 DelegateTool
        # DelegateTool 让 AgentLoop 以为自己在调普通工具，其实是在调子 Agent
        super().__init__(
            name=name,
            llm_client=llm_client,
            tools=[
                DelegateTool(
                    math_agent,
                    "math_agent",
                    "数学专家。输入：算术题或表达式。",
                ),
                DelegateTool(
                    writer_agent,
                    "writer_agent",
                    "写作专家。改写、总结、或把内容讲成通俗的话。",
                ),
                DelegateTool(
                    knowledge_agent,
                    "knowledge_agent",
                    "知识专家。查知识库：公司制度、项目说明、已灌入的文档。",
                ),
                DelegateTool(
                    general_agent,
                    "general_agent",
                    "通用专家。闲聊、常识问答、其他问题。",
                ),
            ],
            session_id=session_id,
            use_memory=True,
            role_prompt=COORD_ROLE,
            max_iterations=max_iterations,
        )
        logger.info(
            "CoordinatorAgent ready (session=%s, sub_agents=%s)",
            (session_id or "new")[:8],
            list(self.sub_agents),
        )
