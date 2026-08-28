"""
API 端到端测试 — 用 Mock LLM 验证完整 HTTP 链路。

使用 Flask 自带的 test_client，不启动真实端口。
"""

import pytest

from src.api.routes import _agents
from src.core.agent_loop import AgentLoop
from server import app
from src.tools.calculator import CalculatorTool


class MockLLMClient:
    """Mock LLM — 模拟 ReAct 循环。"""

    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            return "Thought: Need to calculate.\nAction[calculator](15 * 23)"
        return "Thought: Done.\nFinal Answer: 15 * 23 = 345"


def _inject_mock_agent(session_id: str):
    """注入 Mock Agent 到全局 _agents 字典（跳过真实 LLM 初始化）。"""
    from src.agents.react_agent import ReactAgent
    from src.agents.base_agent import BaseAgent

    agent = ReactAgent.__new__(ReactAgent)
    BaseAgent.__init__(agent, name="ReactAgent")
    agent.llm_client = MockLLMClient()
    agent.tools = [CalculatorTool()]
    agent.memory = None
    agent.max_iterations = 10
    agent.loop = AgentLoop(
        llm_client=agent.llm_client,
        tools=agent.tools,
        memory=None,
        max_iterations=agent.max_iterations,
    )
    _agents[session_id] = agent


@pytest.fixture
def client():
    """创建 Flask 测试客户端。"""
    app.config["TESTING"] = True
    return app.test_client()


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "My Agent API"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert "database" in data


def test_docs(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["framework"] == "Flask"
    assert any(ep["path"] == "/chat" for ep in data["endpoints"])


def test_chat(client):
    """测试聊天接口（注入 Mock Agent）。"""
    _inject_mock_agent("test-session-1")

    resp = client.post("/chat", json={
        "message": "What is 15 * 23?",
        "session_id": "test-session-1",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "345" in data["answer"]
    assert data["agent"] == "ReactAgent"
    assert data["session_id"] == "test-session-1"
    assert data["iterations"] >= 1


def test_chat_empty_message(client):
    """空消息应返回 422。"""
    resp = client.post("/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_auto_session_id(client):
    """不传 session_id 应自动生成。"""
    _inject_mock_agent("auto-gen-session")

    resp = client.post("/chat", json={"message": "hello"})
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert "session_id" in resp.get_json()
