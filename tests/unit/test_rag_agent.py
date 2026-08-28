"""
知识专家走 RAG：主 Agent 委派 knowledge_agent，子 Agent 调用 retrieve。
全程假 LLM，计算器/检索是真的。
"""

from __future__ import annotations

import pytest

from src.agents.react_agent import ReactAgent
from src.rag.store import VectorStore
from src.tools.delegate import DelegateTool
from src.tools.retrieve import RetrieveTool


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._idx = 0

    async def chat(self, messages: list[dict], **kwargs) -> str:
        if self._idx >= len(self._responses):
            return "Final Answer: I don't know."
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


@pytest.mark.asyncio
async def test_knowledge_agent_uses_retrieve_then_answers():
    """
    两层委派：主管只调用 knowledge_agent，知识专家再调用 retrieve。
    假 LLM 按预定格式输出 Action；检索和数字 10 来自真实向量库。
    """
    store = VectorStore(persist_path=None)
    store.add(["正式员工每年享有 10 个工作日年假。"], source="leave-policy.md")

    knowledge_llm = FakeLLMClient(
        [
            "Thought: Look up in KB.\nAction[retrieve](年假天数)",
            "Thought: Got it.\nFinal Answer: 年假是 10 个工作日。",
        ]
    )
    knowledge_agent = ReactAgent(
        name="KnowledgeAgent",
        llm_client=knowledge_llm,
        tools=[RetrieveTool(store=store, top_k=1)],
        use_memory=False,
        max_iterations=5,
    )

    coord_llm = FakeLLMClient(
        [
            "Thought: This is a policy question.\nAction[knowledge_agent](年假有几天)",
            "Thought: Sub-agent answered.\nFinal Answer: 年假是 10 个工作日。",
        ]
    )
    coordinator = ReactAgent(
        name="CoordinatorAgent",
        llm_client=coord_llm,
        tools=[
            DelegateTool(
                knowledge_agent,
                "knowledge_agent",
                "知识专家",
            )
        ],
        use_memory=False,
        max_iterations=5,
    )

    result = await coordinator.run("年假有几天？")
    assert "10" in result
    assert knowledge_llm._idx == 2
    assert coord_llm._idx == 2
