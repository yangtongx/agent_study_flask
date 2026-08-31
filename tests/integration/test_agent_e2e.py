"""
Agent 集成测试 — 端到端流程验证。

=== 什么是集成测试？===
单元测试只测一个模块，集成测试把多个模块组合在一起测试，
验证它们配合工作时是否正确。

这里我们把 AgentLoop + CalculatorTool + MockLLMClient 组合起来，
模拟完整的 ReAct 循环。
"""

import pytest

from src.core.agent_loop import AgentLoop
from src.tools.calculator import CalculatorTool
from src.tools.web_search import WebSearchTool


class MockLLMClient:
    """
    Mock LLM — 模拟 ReAct 循环。

    和单元测试中的 FakeLLMClient 类似，但更贴近真实场景：
    第一轮输出 Action（调用计算器），第二轮输出 Final Answer。
    """

    def __init__(self) -> None:
        self.call_count = 0  # 记录被调用了几次

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """模拟两轮 ReAct 循环。"""
        self.call_count += 1
        if self.call_count == 1:
            # 第一轮：LLM 决定用计算器
            return (
                "Thought: I need to calculate.\n"
                "Action[calculator](15 * 23)"
            )
        # 第二轮：LLM 看到计算结果，给出最终答案
        return (
            "Thought: Got the result.\n"
            "Final Answer: 15 * 23 = 345"
        )


@pytest.mark.asyncio
async def test_react_agent_e2e():
    """端到端测试：Agent 调用计算器后给出最终答案。"""
    mock_client = MockLLMClient()

    # 组装完整的 AgentLoop：Mock LLM + 真实的计算器工具
    loop = AgentLoop(
        llm_client=mock_client,
        tools=[CalculatorTool()],  # 用真实的计算器工具
        max_iterations=5,
    )

    # 执行完整流程
    result = await loop.execute("What is 15 * 23?")

    # 最终答案中应该包含 345
    assert "345" in result


class MockSearchLLMClient:
    """第一轮搜网，第二轮根据 Observation 给答案。"""

    def __init__(self) -> None:
        self.call_count = 0

    async def chat(self, messages: list[dict], **kwargs) -> str:
        self.call_count += 1
        if self.call_count == 1:
            return (
                "Thought: Need current info.\n"
                "Action[web_search](Python 3.13 release date)"
            )
        return (
            "Thought: Search returned the date.\n"
            "Final Answer: Python 3.13.0 was released on October 7, 2024."
        )


@pytest.mark.asyncio
async def test_react_agent_web_search_e2e(monkeypatch):
    """端到端：解析 Action[web_search] → 工具 Observation → Final Answer。"""

    def fake_search(self, query: str) -> list[dict]:
        assert "Python 3.13" in query
        return [
            {
                "title": "Python 3.13.0",
                "href": "https://www.python.org/downloads/",
                "body": "Python 3.13.0 was released on October 7, 2024.",
            }
        ]

    monkeypatch.setattr(WebSearchTool, "_search", fake_search)
    loop = AgentLoop(
        llm_client=MockSearchLLMClient(),
        tools=[WebSearchTool()],
        max_iterations=5,
    )
    result = await loop.execute("When was Python 3.13 released?")
    assert "October 7, 2024" in result
