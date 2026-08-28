"""
AgentScope 2.0 版主 Agent — 分工和手写 CoordinatorAgent 一样。

=== 和手写版差在哪？===

手写版（CoordinatorAgent）：
    LLM 输出纯文本 Thought / Action[name](args) / Final Answer
    我们用正则去解析，再自己调工具。

AgentScope 版（本文件）：
    LLM 走「原生 function calling」（模型按 JSON Schema 选工具）
    AgentScope 自己完成 Thought → 调工具 → Observation 循环。

对外接口故意保持一样：async run(user_input) -> str
所以 Flask / 命令行不用关心背后是哪一套。

=== 结构（和手写版同一张图）===

    用户
      ↓
    ScopeCoordinator（主：只分活）
      ├── math_agent     算术，内部有计算器
      ├── writer_agent   改写 / 总结
      └── general_agent  闲聊、常识
"""

from __future__ import annotations

from types import SimpleNamespace

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.tool import Toolkit

from src.agents.scope_tools import calculator_tool, delegate_tool
from src.configs.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# AgentScope 用原生 tool calling，不要再要求 Thought/Final Answer 英文格式。
MATH_PROMPT = (
    "你是数学专家 MathAgent，专门做算术。"
    "必须使用 calculator 工具计算，不要心算或猜测。"
    "用工具结果里的数字作答，语言和用户一致。"
)

WRITER_PROMPT = (
    "你是写作专家 WriterAgent，专门改写、总结、把话讲明白。"
    "你没有工具，直接作答。"
    "用和任务相同的语言回复。"
)

GENERAL_PROMPT = (
    "你是通用专家 GeneralAgent，负责闲聊和常识问答。"
    "你没有工具，直接作答。"
    "用和用户相同的语言回复。"
)

COORD_PROMPT = """你是主 Agent（ScopeCoordinator），负责给专家分活，不要自己做专家的工作。

分工：
- 算术、公式、数字计算 → math_agent
- 改写、总结、翻译、通俗解释 → writer_agent
- 闲聊、常识、其他问题 → general_agent

可以连续调用多个子 Agent（例如先 math_agent 再 writer_agent）。
拿到足够结果之后，直接回答用户。
除非用户问内部原理，否则不要提及工具名。"""


def build_chat_model() -> OpenAIChatModel:
    """
    用 .env 里的 DeepSeek（或任何 OpenAI 兼容接口）创建 AgentScope 模型。

    stream=False：Flask / 命令行要的是一整段回复，不要边生成边推流。
    """
    settings = get_settings()
    credential = OpenAICredential(
        id="project-llm",
        name="project-llm",
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
    )
    return OpenAIChatModel(
        credential=credential,
        model=settings.llm_model,
        stream=False,
    )


class ScopeCoordinator:
    """
    AgentScope 实现的主 Agent。

    不继承手写的 BaseAgent：那边绑着我们自己的 LLM 客户端和工具基类。
    只要有 name、run()、loop._iteration_count，HTTP 层就能用。
    """

    name = "ScopeCoordinator"

    def __init__(
        self,
        session_id: str | None = None,
        *,
        max_iterations: int | None = None,
        model: OpenAIChatModel | None = None,
        coordinator: Agent | None = None,
    ) -> None:
        settings = get_settings()
        iters = max_iterations or settings.agent_max_iterations
        self.session_id = session_id
        # 兼容 Flask 的 ChatResponse.iterations（AgentScope 不暴露手写 loop 计数）
        self.loop = SimpleNamespace(_iteration_count=0)

        if coordinator is not None:
            self._agent = coordinator
            self.sub_agents = {}
            return

        chat_model = model or build_chat_model()
        react = ReActConfig(max_iters=iters)

        math_agent = Agent(
            name="MathAgent",
            system_prompt=MATH_PROMPT,
            model=chat_model,
            toolkit=Toolkit(tools=[calculator_tool()]),
            react_config=react,
        )
        writer_agent = Agent(
            name="WriterAgent",
            system_prompt=WRITER_PROMPT,
            model=chat_model,
            toolkit=Toolkit(tools=[]),
            react_config=react,
        )
        general_agent = Agent(
            name="GeneralAgent",
            system_prompt=GENERAL_PROMPT,
            model=chat_model,
            toolkit=Toolkit(tools=[]),
            react_config=react,
        )

        self.sub_agents = {
            "math_agent": math_agent,
            "writer_agent": writer_agent,
            "general_agent": general_agent,
        }

        self._agent = Agent(
            name=self.name,
            system_prompt=COORD_PROMPT,
            model=chat_model,
            toolkit=Toolkit(
                tools=[
                    delegate_tool(
                        math_agent,
                        "math_agent",
                        "数学专家。输入：算术题或表达式。",
                    ),
                    delegate_tool(
                        writer_agent,
                        "writer_agent",
                        "写作专家。改写、总结、或把内容讲成通俗的话。",
                    ),
                    delegate_tool(
                        general_agent,
                        "general_agent",
                        "通用专家。闲聊、常识问答、其他问题。",
                    ),
                ],
            ),
            react_config=react,
        )
        logger.info(
            "ScopeCoordinator ready (session=%s, sub_agents=%s)",
            (session_id or "new")[:8],
            list(self.sub_agents),
        )

    async def run(self, user_input: str) -> str:
        """处理用户输入，返回最终回复文本。"""
        reply = await self._agent.reply(UserMsg(name="user", content=user_input))
        text = reply.get_text_content() if reply is not None else ""
        self.loop._iteration_count = 1
        return (text or "").strip()
