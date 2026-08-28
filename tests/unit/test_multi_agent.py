"""
多 Agent 单元测试 — 主 Agent 把任务委派给子 Agent。

=== 测什么？===
主 Agent（Coordinator）不自己算数，而是调用 math_agent 子 Agent。
子 Agent 再用计算器，把结果交回主 Agent，主 Agent 给出 Final Answer。
全程用假 LLM，不调用真实 API。
"""

import pytest

from src.agents.react_agent import ReactAgent
from src.core.agent_loop import AgentLoop
from src.tools.calculator import CalculatorTool
from src.tools.delegate import DelegateTool


class FakeLLMClient:
    """按预设顺序返回回复的假 LLM。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._idx = 0
        self.messages_seen: list[list[dict]] = []

    async def chat(self, messages: list[dict], **kwargs) -> str:
        self.messages_seen.append(messages)
        if self._idx >= len(self._responses):
            return "Final Answer: I don't know."
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


@pytest.mark.asyncio
async def test_coordinator_delegates_math_to_sub_agent():
    """
    用户问乘法 → 主 Agent 调用 math_agent → 子 Agent 用计算器 → 主 Agent 汇总答案。
    """
    math_llm = FakeLLMClient([
        "Thought: I will use the calculator.\nAction[calculator](15 * 23)",
        "Thought: Got it.\nFinal Answer: 15 * 23 = 345",
    ])
    math_agent = ReactAgent(
        name="MathAgent",
        llm_client=math_llm,
        tools=[CalculatorTool()],
        memory=None,
        use_memory=False,
        max_iterations=5,
    )

    coord_llm = FakeLLMClient([
        "Thought: This is math, delegate.\nAction[math_agent](15 * 23)",
        "Thought: Sub-agent returned the result.\nFinal Answer: 15 * 23 = 345",
    ])
    coordinator = ReactAgent(
        name="CoordinatorAgent",
        llm_client=coord_llm,
        tools=[
            DelegateTool(
                agent=math_agent,
                name="math_agent",
                description="Specialist for arithmetic.",
            )
        ],
        memory=None,
        use_memory=False,
        max_iterations=5,
    )

    result = await coordinator.run("What is 15 * 23?")

    assert "345" in result
    assert math_llm._idx == 2
    assert coord_llm._idx == 2
