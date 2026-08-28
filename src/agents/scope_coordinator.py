"""
AgentScope 2.0 版主 Agent — 分工和手写 CoordinatorAgent 一样。

=== 和手写版差在哪？===

手写版（CoordinatorAgent）：
    LLM 输出纯文本 Thought / Action[name](args) / Final Answer
    我们用正则去解析，再自己调工具（见 src/core/agent_loop.py）。

AgentScope 版（本文件）：
    LLM 走「原生 function calling」（模型按 JSON Schema 选工具）
    AgentScope 的 Agent.reply() 自己完成：想一想 → 调工具 → 看结果 → 再想。

对外接口故意保持一样：async run(user_input) -> str
所以 Flask / 命令行不用关心背后是哪一套。

=== 结构（和手写版同一张图）===

    用户
      ↓
    ScopeCoordinator（主：只分活）
      ├── math_agent     算术，内部有计算器
      ├── writer_agent   改写 / 总结
      └── general_agent  闲聊、常识

=== 例子 ===
用户：15 乘 23 等于多少？

1. 主 Agent 决定调用工具 math_agent
2. math_agent 再调用 calculator → "15 * 23 = 345"
3. 主 Agent 拿到结果，用自然语言回答用户

手写版这一步靠正则抠 Action[...]；这里靠模型返回的 tool_calls JSON。
"""

from __future__ import annotations

# SimpleNamespace：把普通对象当成「有属性的盒子」用。
# Flask 要读 agent.loop._iteration_count，AgentScope 没有这个字段，
# 我们就造一个假 loop，避免改 HTTP 层。
from types import SimpleNamespace

# Agent：AgentScope 2.0 统一的智能体类（不再叫 ReActAgent）
# ReActConfig：推理循环配置，这里只用 max_iters（最多转几圈）
from agentscope.agent import Agent, ReActConfig

# OpenAICredential：API Key + base_url。DeepSeek 兼容 OpenAI 协议，所以用这一套
from agentscope.credential import OpenAICredential

# UserMsg：构造一条「用户说的话」，交给 agent.reply()
from agentscope.message import UserMsg

# OpenAIChatModel：按 OpenAI Chat Completions 调模型（可换 DeepSeek / 本地 vLLM）
from agentscope.model import OpenAIChatModel

# Toolkit：工具箱。Agent 能用哪些工具，全在这里注册
from agentscope.tool import Toolkit

from src.agents.scope_tools import calculator_tool, delegate_tool
from src.configs.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 人设（system prompt）
# AgentScope 用原生 tool calling，不要再要求 Thought / Final Answer 英文格式。
# 那些关键词是手写正则解析用的，写在这里反而会把官方 Agent 搞糊涂。
# ---------------------------------------------------------------------------

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

    === 为什么用 OpenAIChatModel 而不是 DeepSeekChatModel？===
    本项目的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL 本来就是按 OpenAI 兼容协议配的。
    OpenAIChatModel 可以直接吃这三项，换别的兼容服务时不用改代码。

    stream=False：Flask / 命令行要的是一整段回复，不要边生成边推流。
    id / name：AgentScope 的凭证对象必填一个标识，随便起个稳定名字即可。
    """
    settings = get_settings()
    credential = OpenAICredential(
        id="project-llm",
        name="project-llm",
        api_key=settings.llm_api_key,
        # 空字符串转成 None，让 SDK 走默认地址
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
    只要有下面三个东西，HTTP 层就能当它和 CoordinatorAgent 一样用：
        - name
        - async run(user_input) -> str
        - loop._iteration_count
    """

    # 类属性：所有实例都叫这个名字，会出现在 /chat 返回的 agent 字段里
    name = "ScopeCoordinator"

    def __init__(
        self,
        session_id: str | None = None,
        *,
        max_iterations: int | None = None,
        model: OpenAIChatModel | None = None,
        coordinator: Agent | None = None,
    ) -> None:
        """
        Args:
            session_id: 会话 ID。同一会话复用同一个 ScopeCoordinator 时，
                        AgentScope 内部的 AgentState 会记住对话（框架自带记忆）。
            max_iterations: 主/子 Agent 各自最多推理几轮。不传则读 .env。
            model: 测试或高级用法可注入已经建好的模型；不传则按 .env 创建。
            coordinator: 测试专用。传入假 Agent 就能跳过真实 LLM，只测 run() 外壳。
        """
        settings = get_settings()
        # 没传 max_iterations 就用配置中心的默认值（一般是 10）
        iters = max_iterations or settings.agent_max_iterations
        self.session_id = session_id
        # Flask 的 ChatResponse 需要 iterations。
        # AgentScope 不暴露手写 AgentLoop 的计数，这里放一个兼容用的假 loop。
        self.loop = SimpleNamespace(_iteration_count=0)

        # 测试路径：不创建四个真实 Agent，直接用注入的假对象
        if coordinator is not None:
            self._agent = coordinator
            self.sub_agents = {}
            return

        # 四个 Agent 共用一个模型客户端（它本身无会话状态，只负责发 HTTP）
        chat_model = model or build_chat_model()
        # max_iters：防止模型一直调工具、永远不给最终回复
        react = ReActConfig(max_iters=iters)

        # --- 三个专家 ---
        # 数学专家：工具箱里只有计算器
        math_agent = Agent(
            name="MathAgent",
            system_prompt=MATH_PROMPT,
            model=chat_model,
            toolkit=Toolkit(tools=[calculator_tool()]),
            react_config=react,
        )
        # 写作专家：空工具箱，只生成文字
        writer_agent = Agent(
            name="WriterAgent",
            system_prompt=WRITER_PROMPT,
            model=chat_model,
            toolkit=Toolkit(tools=[]),
            react_config=react,
        )
        # 通用专家：同样没有工具
        general_agent = Agent(
            name="GeneralAgent",
            system_prompt=GENERAL_PROMPT,
            model=chat_model,
            toolkit=Toolkit(tools=[]),
            react_config=react,
        )

        # 给日志 / 健康检查用：主 Agent 能调度谁
        self.sub_agents = {
            "math_agent": math_agent,
            "writer_agent": writer_agent,
            "general_agent": general_agent,
        }

        # --- 主管 ---
        # 主管的「工具」就是三个专家。delegate_tool 内部会调用子 Agent.reply()
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
        """
        处理用户输入，返回最终回复文本。

        这是和手写 CoordinatorAgent.run() 对齐的入口：
        Flask / 命令行都只调用这一行，不需要知道内部是 AgentScope。

        UserMsg(name="user", content=...)：
            name 是发送者标识，content 可以是普通字符串（框架会包成 TextBlock）。
        reply() 是异步的，内部可能多次调 LLM、多次调工具，全部结束后才返回。
        get_text_content() 把消息对象收成纯文本，方便 print / 塞进 JSON。
        """
        reply = await self._agent.reply(UserMsg(name="user", content=user_input))
        text = reply.get_text_content() if reply is not None else ""
        # 至少标记「跑过一轮」，让 /chat 的 iterations 字段不是 0
        self.loop._iteration_count = 1
        return (text or "").strip()
