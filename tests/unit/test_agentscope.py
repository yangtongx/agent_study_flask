"""
AgentScope 2.0 接入测试 — 不调用真实 LLM。

测三件事：
1. 计算器包装后仍能算
2. 自定义工具默认自动允许（不会卡在「请用户确认」）
3. ScopeCoordinator.run() 对外接口和手写版一样（可注入假 Agent）
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentscope.permission import PermissionBehavior

from src.agents.factory import create_main_agent, display_agent_name, get_backend
from src.agents.scope_coordinator import ScopeCoordinator
from src.agents.scope_tools import calculator_tool


class FakeMsg:
    def __init__(self, text: str) -> None:
        self._text = text

    def get_text_content(self) -> str:
        return self._text


class FakeScopeAgent:
    name = "FakeCoordinator"

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def reply(self, inputs) -> FakeMsg:
        content = inputs.content
        if isinstance(content, str):
            self.seen.append(content)
        else:
            self.seen.append(str(content))
        return FakeMsg("15 * 23 = 345")


@pytest.mark.asyncio
async def test_calculator_tool_wrapped_for_agentscope():
    tool = calculator_tool()
    chunk = await tool.call(expression="15 * 23")
    text = chunk.content[0]["text"] if isinstance(chunk.content[0], dict) else chunk.content[0].text
    assert "345" in text


@pytest.mark.asyncio
async def test_allow_function_tool_auto_allows():
    tool = calculator_tool()
    decision = await tool.check_permissions({})
    assert decision.behavior == PermissionBehavior.ALLOW


@pytest.mark.asyncio
async def test_scope_coordinator_run_uses_injected_agent():
    fake = FakeScopeAgent()
    agent = ScopeCoordinator(session_id="test", coordinator=fake)
    result = await agent.run("What is 15 * 23?")
    assert "345" in result
    assert agent.name == "ScopeCoordinator"
    assert agent.loop._iteration_count >= 1
    assert fake.seen


def test_factory_default_is_handmade(monkeypatch):
    monkeypatch.setattr("src.agents.factory.get_backend", lambda: "handmade")
    agent = create_main_agent(session_id="factory-test")
    assert agent.name == "CoordinatorAgent"


def test_display_name_follows_backend(monkeypatch):
    monkeypatch.setattr("src.agents.factory.get_backend", lambda: "agentscope")
    assert display_agent_name() == "ScopeCoordinator"
    monkeypatch.setattr("src.agents.factory.get_backend", lambda: "handmade")
    assert display_agent_name() == "CoordinatorAgent"


def test_get_backend_fallback(monkeypatch):
    monkeypatch.setattr(
        "src.agents.factory.get_settings",
        lambda: SimpleNamespace(agent_backend="not-a-real-backend"),
    )
    assert get_backend() == "handmade"
