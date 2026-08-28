"""
主 Agent（Coordinator）+ 三个子 Agent。

=== 多 Agent 怎么分工？===

    用户
      ↓
    CoordinatorAgent（主：只负责分活，自己不算、不写长文）
      ├── math_agent     算术，内部有计算器
      ├── writer_agent   改写 / 总结 / 通俗解释
      └── general_agent  闲聊、常识问答

主 Agent 的「工具」其实是子 Agent（见 DelegateTool）。
子 Agent 各自再跑一轮自己的 ReAct 循环，把答案交回主 Agent。

=== 例子 ===
用户：15 乘 23 等于多少？再用一句话说人话。

主 Agent 第 1 轮：Action[math_agent](15 * 23)
  └─ 子 Agent 用计算器 → 345
主 Agent 第 2 轮：Action[writer_agent](把 345 说成一句人话)
  └─ 子 Agent → 「15 乘 23 等于 345。」
主 Agent 第 3 轮：Final Answer: ...
"""

from __future__ import annotations

from src.agents.react_agent import ReactAgent
from src.llm.base_client import BaseLLMClient
from src.tools.calculator import CalculatorTool
from src.tools.delegate import DelegateTool
from src.utils.logger import get_logger

logger = get_logger(__name__)

MATH_ROLE = (
    "You are MathAgent, a specialist in arithmetic. "
    "Always use the calculator tool. Do not guess the result. "
    "After you see the Observation, output Final Answer with the number."
)

WRITER_ROLE = (
    "You are WriterAgent, a specialist in writing. "
    "Rewrite, summarize, or explain the given task clearly. "
    "Always output Final Answer. Use the same language as the task."
)

GENERAL_ROLE = (
    "You are GeneralAgent, a general Q&A specialist. "
    "Answer questions, chit-chat, and share common knowledge. "
    "Always output Final Answer. Use the same language as the user."
)

COORD_ROLE = """You are CoordinatorAgent, the MAIN agent of a multi-agent system.
You do NOT do specialist work yourself. You DELEGATE tasks to sub-agents.

Routing:
- Arithmetic, formulas, numeric computation → math_agent
- Rewrite, summarize, translate, explain in plain language → writer_agent
- General knowledge, chit-chat, everything else → general_agent

You may call several sub-agents in sequence (for example math_agent then writer_agent).
When you have enough Observations, give the user a Final Answer.
Do not mention internal tool names unless the user asks how you work."""


class CoordinatorAgent(ReactAgent):
    """
    主 Agent：把用户任务分给子 Agent。

    HTTP / 命令行入口创建的就是这个类。
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
        max_iterations: int = 10,
    ) -> None:
        math_agent = ReactAgent(
            name="MathAgent",
            llm_client=math_llm,
            tools=[CalculatorTool()],
            use_memory=False,
            role_prompt=MATH_ROLE,
            max_iterations=max_iterations,
        )
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

        self.sub_agents = {
            "math_agent": math_agent,
            "writer_agent": writer_agent,
            "general_agent": general_agent,
        }

        super().__init__(
            name=name,
            llm_client=llm_client,
            tools=[
                DelegateTool(
                    math_agent,
                    "math_agent",
                    "Specialist for arithmetic. Input: a math question or expression.",
                ),
                DelegateTool(
                    writer_agent,
                    "writer_agent",
                    "Specialist for rewriting, summarizing, or explaining in plain language.",
                ),
                DelegateTool(
                    general_agent,
                    "general_agent",
                    "Specialist for general questions and conversation.",
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
