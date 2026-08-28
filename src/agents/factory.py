"""
主 Agent 工厂 — 按配置选择「手写 ReAct」或「AgentScope 2.0」。

=== 什么是工厂？===
调用方只说「给我一个主 Agent」，不说「new 哪一个类」。
就像去咖啡店点拿铁：你不管咖啡机怎么做，只要拿到那杯咖啡。

=== 为什么要工厂？===
Flask（routes.py）和命令行（main.py）只关心：
    agent = create_main_agent(session_id=...)
    answer = await agent.run("你好")

背后用哪套实现，用环境变量 AGENT_BACKEND 切换：

    handmade   → CoordinatorAgent（自己解析 Thought/Action 文本）
    agentscope → ScopeCoordinator（官方框架，原生 tool calling）

默认 handmade：原有测试、假 LLM 注入都还能跑。
切换时不用改 Flask 路由，只改 .env 再重启。
"""

from __future__ import annotations

from typing import Any, Protocol

from src.agents.coordinator_agent import CoordinatorAgent
from src.configs.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MainAgent(Protocol):
    """
    HTTP / 命令行需要的最小接口。

    === 什么是 Protocol？===
    一种「鸭子类型」的类型标注：不要求继承某个基类，
    只要对象有这些属性和方法，就算合格。

    CoordinatorAgent 和 ScopeCoordinator 都满足：
        - name: 出现在 /chat 返回 JSON 的 agent 字段
        - loop._iteration_count: 出现在 iterations 字段
        - async run(str) -> str: 真正聊天
    """

    name: str
    loop: Any

    async def run(self, user_input: str) -> str: ...


def get_backend() -> str:
    """
    读取 AGENT_BACKEND，只允许 handmade / agentscope。

    写错了（比如 agent-scope、AgentScope）会打警告并回落到 handmade，
    避免服务直接启动失败。
    """
    raw = (get_settings().agent_backend or "handmade").strip().lower()
    if raw in ("handmade", "agentscope"):
        return raw
    logger.warning("Unknown AGENT_BACKEND=%s, fallback to handmade", raw)
    return "handmade"


def display_agent_name() -> str:
    """
    健康检查 /health 里展示的 Agent 名称。

    这时可能还没创建过实例，所以不能读 agent.name，只能按配置推断。
    """
    return "ScopeCoordinator" if get_backend() == "agentscope" else "CoordinatorAgent"


def create_main_agent(
    session_id: str | None = None,
    **kwargs: Any,
) -> MainAgent:
    """
    创建主 Agent。

    Args:
        session_id: 会话 ID。同一 ID 应在路由层缓存实例，工厂每次调用都会 new 一个。
        **kwargs: 只传给手写 CoordinatorAgent（例如测试里注入假 LLM：
                  llm_client=..., math_llm=...）。
                  AgentScope 后端走自己的 OpenAIChatModel，忽略这些参数。

    Returns:
        一个能 run() 的主 Agent。

    === 为什么 AgentScope 用延迟 import？===
    from src.agents.scope_coordinator import ... 会加载 agentscope 整包，比较慢。
    默认 handmade 时根本不需要它，所以写在 if 里面，用到再导入。
    """
    backend = get_backend()
    if backend == "agentscope":
        from src.agents.scope_coordinator import ScopeCoordinator

        logger.info("Creating ScopeCoordinator (AgentScope 2.0)")
        return ScopeCoordinator(session_id=session_id)

    logger.info("Creating CoordinatorAgent (handmade ReAct)")
    return CoordinatorAgent(session_id=session_id, **kwargs)
