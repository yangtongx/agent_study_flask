"""Agent 核心模块单元测试。

=== 什么是单元测试？===
单元测试是对"最小代码单元"（一个函数/方法）做独立测试。
不依赖外部服务（如 LLM API），用假对象（Mock）模拟依赖。

=== 什么是 Fake/Mock？===
我们不想在测试时真的调用 OpenAI API（要花钱、要网络），
所以创建一个 FakeLLMClient，它实现了 chat() 方法，
但返回预设的固定回复。
"""

import pytest

from src.core.agent_loop import AgentLoop
from src.utils.exceptions import MaxIterationsError


class FakeLLMClient:
    """
    假 LLM 客户端 — 用于测试。

    它实现了和 BaseLLMClient 相同的 chat() 方法，
    但不从网络获取回复，而是返回预设的固定文本。

    这样我们可以精确控制 LLM 的"回复"来测试各种场景：
    - 场景1：LLM 第一轮就给出 Final Answer
    - 场景2：LLM 一直不给 Final Answer（测试超时保护）
    """

    def __init__(self, responses: list[str]) -> None:
        """
        Args:
            responses: 预设回复列表，按调用顺序依次返回。
        """
        self._responses = responses
        self._idx = 0  # 当前回复的索引

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """模拟 LLM 的 chat 方法，返回预设回复。"""
        # 如果预设回复用完了，返回默认回复
        if self._idx >= len(self._responses):
            return "Final Answer: I don't know."

        # 取出当前回复，索引前进
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


@pytest.mark.asyncio
async def test_final_answer_immediate():
    """
    测试场景1：LLM 直接给出 Final Answer。

    预期行为：LLM 第一轮就输出 "Final Answer: 42"，
    AgentLoop 应立即返回 "42"，不再循环。
    """
    # 创建假客户端，预设回复包含 Final Answer
    client = FakeLLMClient(["Thought: easy.\nFinal Answer: 42"])

    # 创建 AgentLoop，不用工具，最多循环 3 次
    loop = AgentLoop(llm_client=client, tools=[], max_iterations=3)

    # 执行
    result = await loop.execute("What is the answer?")

    # 断言：结果应该是 "42"
    assert result == "42"


@pytest.mark.asyncio
async def test_max_iterations_error():
    """
    测试场景2：超过最大迭代次数。

    预期行为：LLM 一直不输出 Final Answer，
    超过 max_iterations 次后应该抛出 MaxIterationsError。
    """
    # 创建假客户端，回复永远不包含 Final Answer
    # ["Thought: hmm"] * 10 表示重复 10 次
    client = FakeLLMClient(["Thought: hmm"] * 10)

    # max_iterations=2，只允许循环 2 次
    loop = AgentLoop(llm_client=client, tools=[], max_iterations=2)

    # pytest.raises 断言会抛出指定异常
    with pytest.raises(MaxIterationsError):
        await loop.execute("loop forever")
