"""
AgentScope 2.0 接入测试 — 不调用真实 LLM。

测三件事：
1. 计算器包装后仍能算（包装层没把 AST 计算器弄坏）
2. 自定义工具默认自动允许（不会卡在「请用户确认」）
3. ScopeCoordinator.run() 对外接口和手写版一样（可注入假 Agent）

另外测工厂：默认 handmade、名字跟着后端变、非法值回落 handmade。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentscope.permission import PermissionBehavior

from src.agents.factory import create_main_agent, display_agent_name, get_backend
from src.agents.scope_coordinator import ScopeCoordinator
from src.agents.scope_tools import calculator_tool


class FakeMsg:
    """
    假消息：只实现 get_text_content()。

    AgentScope 真消息还有很多字段，run() 只用得到纯文本，测试不必造完整对象。
    """

    def __init__(self, text: str) -> None:
        self._text = text

    def get_text_content(self) -> str:
        return self._text


class FakeScopeAgent:
    """
    假主管：假装自己是 agentscope.agent.Agent。

    不调 LLM，固定回复 "15 * 23 = 345"。
    seen 记录收到过什么，用来确认 run() 真的把用户输入传进去了。
    """

    name = "FakeCoordinator"

    def __init__(self) -> None:
        self.seen: list[str] = []

    async def reply(self, inputs) -> FakeMsg:
        # UserMsg.content 可能是字符串，也可能是 TextBlock 列表
        content = inputs.content
        if isinstance(content, str):
            self.seen.append(content)
        else:
            self.seen.append(str(content))
        return FakeMsg("15 * 23 = 345")


@pytest.mark.asyncio
async def test_calculator_tool_wrapped_for_agentscope():
    """包装后的计算器仍走 AST 求值，15 * 23 必须得到 345。"""
    tool = calculator_tool()
    # AgentScope 用关键字参数调用，不是手写版的 run("15 * 23")
    chunk = await tool.call(expression="15 * 23")
    # ToolChunk.content 里是 TextBlock，可能是对象也可能是 dict
    text = chunk.content[0]["text"] if isinstance(chunk.content[0], dict) else chunk.content[0].text
    assert "345" in text


@pytest.mark.asyncio
async def test_allow_function_tool_auto_allows():
    """学习用包装必须是 ALLOW，否则 Flask 会卡在等待用户确认。"""
    tool = calculator_tool()
    decision = await tool.check_permissions({})
    assert decision.behavior == PermissionBehavior.ALLOW


@pytest.mark.asyncio
async def test_scope_coordinator_run_uses_injected_agent():
    """注入假 Agent 后，run() 仍返回文本，且对外名字仍是 ScopeCoordinator。"""
    fake = FakeScopeAgent()
    agent = ScopeCoordinator(session_id="test", coordinator=fake)
    result = await agent.run("What is 15 * 23?")
    assert "345" in result
    assert agent.name == "ScopeCoordinator"
    assert agent.loop._iteration_count >= 1
    assert fake.seen


def test_factory_default_is_handmade(monkeypatch):
    """强制 handmade 时，工厂必须给出 CoordinatorAgent（不加载 AgentScope 主类）。"""
    # monkeypatch：测试期间把 get_backend 换成固定返回，测完自动恢复
    monkeypatch.setattr("src.agents.factory.get_backend", lambda: "handmade")
    agent = create_main_agent(session_id="factory-test")
    assert agent.name == "CoordinatorAgent"


def test_display_name_follows_backend(monkeypatch):
    """/health 展示的名字必须跟 AGENT_BACKEND 一致。"""
    monkeypatch.setattr("src.agents.factory.get_backend", lambda: "agentscope")
    assert display_agent_name() == "ScopeCoordinator"
    monkeypatch.setattr("src.agents.factory.get_backend", lambda: "handmade")
    assert display_agent_name() == "CoordinatorAgent"


def test_get_backend_fallback(monkeypatch):
    """拼写错误的 AGENT_BACKEND 不能把服务弄崩，应回落到 handmade。"""
    monkeypatch.setattr(
        "src.agents.factory.get_settings",
        lambda: SimpleNamespace(agent_backend="not-a-real-backend"),
    )
    assert get_backend() == "handmade"
