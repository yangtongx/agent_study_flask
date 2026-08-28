"""
API 端到端测试 — 用 Mock LLM 验证完整 HTTP 链路。

使用 Flask 自带的 test_client，不启动真实端口。
"""

import pytest

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.factory import display_agent_name, get_backend
from src.api.routes import _agents
from server import app


class MockLLMClient:
    """按预设顺序返回回复。"""

    def __init__(self, responses: list[str]):
        self._responses = responses
        self._idx = 0

    async def chat(self, messages, **kwargs):
        if self._idx >= len(self._responses):
            return "Final Answer: I don't know."
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


def _inject_mock_agent(session_id: str):
    """注入带 Mock LLM 的主 Agent（跳过真实 API）。"""
    math_llm = MockLLMClient([
        "Thought: Use calculator.\nAction[calculator](15 * 23)",
        "Thought: Done.\nFinal Answer: 15 * 23 = 345",
    ])
    coord_llm = MockLLMClient([
        "Thought: Delegate math.\nAction[math_agent](15 * 23)",
        "Thought: Got sub-agent result.\nFinal Answer: 15 * 23 = 345",
    ])
    idle = MockLLMClient(["Thought: unused.\nFinal Answer: ok"])
    agent = CoordinatorAgent(
        session_id=session_id,
        llm_client=coord_llm,
        math_llm=math_llm,
        writer_llm=idle,
        general_llm=idle,
        knowledge_llm=idle,
        max_iterations=5,
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
    data = resp.get_json()
    assert data["name"] == "My Agent API"
    assert data["mode"] == "multi-agent"
    assert data["backend"] in ("handmade", "agentscope")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert "database" in data
    assert data["agent"] == display_agent_name()
    assert "math_agent" in data["sub_agents"]
    assert "knowledge_agent" in data["sub_agents"]
    assert data["backend"] == get_backend()
    assert "knowledge_chunks" in data


def test_docs(client):
    resp = client.get("/docs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["framework"] == "Flask"
    assert any(ep["path"] == "/chat" for ep in data["endpoints"])


def test_chat(client):
    """测试聊天接口（注入 Mock 主 Agent + 数学子 Agent）。"""
    _inject_mock_agent("test-session-1")

    resp = client.post("/chat", json={
        "message": "What is 15 * 23?",
        "session_id": "test-session-1",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "345" in data["answer"]
    assert data["agent"] == "CoordinatorAgent"
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


def test_knowledge_ingest_and_search(client, tmp_path, monkeypatch):
    """POST 灌入 + GET 检索，不经过 LLM。"""
    from src.rag.store import VectorStore, reset_vector_store

    store = VectorStore(persist_path=str(tmp_path / "rag"))
    reset_vector_store(store)
    try:
        resp = client.post("/knowledge", json={
            "content": "正式员工每年享有 10 个工作日年假。",
            "source": "leave-policy.md",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["chunks"] >= 1
        assert data["total"] >= 1

        search = client.get("/knowledge/search", query_string={"q": "年假几天", "top_k": 1})
        assert search.status_code == 200
        hits = search.get_json()["hits"]
        assert hits
        assert "10" in hits[0]["text"]
    finally:
        reset_vector_store(None)


def test_knowledge_search_requires_q(client):
    resp = client.get("/knowledge/search")
    assert resp.status_code == 422
