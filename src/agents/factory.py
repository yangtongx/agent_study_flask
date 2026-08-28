"""
主 Agent 工厂 — 按配置选择「手写 ReAct」或「AgentScope 2.0」。

=== 为什么要工厂？===
Flask 和命令行只关心「给我一个能 run() 的主 Agent」。
背后用哪套实现，用环境变量 AGENT_BACKEND 切换：

    handmade   → CoordinatorAgent（自己解析 Thought/Action 文本）
    agentscope → ScopeCoordinator（官方框架，原生 tool calling）

默认 handmade：原有测试、假 LLM 注入都还能跑。
"""

from __future__ import annotations

from typing import Any, Protocol

from src.agents.coordinator_agent import CoordinatorAgent
from src.configs.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MainAgent(Protocol):
    """HTTP / 命令行需要的最小接口。"""

    name: str
    loop: Any

    async def run(self, user_input: str) -> str: ...


def get_backend() -> str:
    """读取 AGENT_BACKEND，非法值回落到 handmade。"""
    raw = (get_settings().agent_backend or "handmade").strip().lower()
    if raw in ("handmade", "agentscope"):
        return raw
    logger.warning("Unknown AGENT_BACKEND=%s, fallback to handmade", raw)
    return "handmade"


def display_agent_name() -> str:
    """健康检查里展示的 Agent 名称。"""
    return "ScopeCoordinator" if get_backend() == "agentscope" else "CoordinatorAgent"


def create_main_agent(
    session_id: str | None = None,
    **kwargs: Any,
) -> MainAgent:
    """
    创建主 Agent。

    kwargs 只传给手写 CoordinatorAgent（例如测试里注入假 LLM）。
    AgentScope 后端走自己的模型配置，忽略这些参数。
    """
    backend = get_backend()
    if backend == "agentscope":
        from src.agents.scope_coordinator import ScopeCoordinator

        logger.info("Creating ScopeCoordinator (AgentScope 2.0)")
        return ScopeCoordinator(session_id=session_id)

    logger.info("Creating CoordinatorAgent (handmade ReAct)")
    return CoordinatorAgent(session_id=session_id, **kwargs)
