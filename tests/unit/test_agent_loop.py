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
        self.calls: list[list[dict]] = []  # 每次 chat() 收到的 messages

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """模拟 LLM 的 chat 方法，返回预设回复。"""
        # 记下每次调用时的完整消息，方便断言循环注入了什么
        self.calls.append([dict(m) for m in messages])

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

    # 断言：结果里既有 Thought 也有最终数字
    assert "Thought:" in result
    assert "easy" in result
    assert "42" in result


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


@pytest.mark.asyncio
async def test_plain_reply_treated_as_final_answer():
    """
    测试场景3：用户问「你叫什么」，LLM 直接用自然语言回答，没有 ReAct 标记。

    预期行为：把它当成最终答案返回，不要注入「请用 Action 格式」
    把对话劫持成格式说明。
    """
    client = FakeLLMClient(["我是 ReactAgent，一个基于 ReAct 的助手。"])
    loop = AgentLoop(llm_client=client, tools=[], max_iterations=3)

    result = await loop.execute("你叫什么")

    assert "ReactAgent" in result
    assert "Action[" not in result
    assert loop._iteration_count == 1


@pytest.mark.asyncio
async def test_incomplete_thought_retry_allows_final_answer():
    """
    测试场景4：第一轮只有 Thought、没有 Action/Final Answer。

    预期行为：重试提示必须同时允许 Final Answer，不能只逼模型输出 Action。
    否则模型会把提示当成新问题，开始解释格式。
    """
    client = FakeLLMClient([
        "Thought: The user asked my name.",
        "Thought: I can answer directly.\nFinal Answer: 我叫 ReactAgent",
    ])
    loop = AgentLoop(llm_client=client, tools=[], max_iterations=3)

    result = await loop.execute("你叫什么")

    assert "ReactAgent" in result
    assert len(client.calls) == 2
    hint = client.calls[1][-1]["content"]
    assert "Final Answer" in hint


def test_system_prompt_covers_identity_and_direct_answer():
    """
    测试场景5：system prompt 要告诉模型自己的名字，
    简单问题（名字、闲聊）应直接 Final Answer，不要解释工具格式。
    """
    loop = AgentLoop(llm_client=FakeLLMClient([]), tools=[], max_iterations=1)
    prompt = loop._build_system_prompt()

    assert "小宝" in prompt
    assert "你的名字是" in prompt
    assert "Final Answer" in prompt
    assert "Action[" in prompt
    assert "可用工具" in prompt


@pytest.mark.asyncio
async def test_execute_wraps_user_input_with_task_template():
    """发给 LLM 的当前用户消息应来自 task.md，而不是裸输入。"""
    client = FakeLLMClient(["Thought: ok\nFinal Answer: 我叫 ReactAgent"])
    loop = AgentLoop(llm_client=client, tools=[], max_iterations=2)

    await loop.execute("你叫什么")

    user_msg = client.calls[0][-1]["content"]
    assert "你叫什么" in user_msg
    assert "用户输入" in user_msg


def test_extract_thought_stops_before_action():
    """Thought 应停在 Action / Final Answer 之前，不要把工具调用吞进去。"""
    text = "Thought: 需要计算。\nAction[calculator](15 * 23)"
    assert AgentLoop._extract_thought(text) == "需要计算。"
    final = "Thought: 算出来了。\nFinal Answer: 345"
    assert AgentLoop._extract_thought(final) == "算出来了。"
    assert AgentLoop._extract_thought("我叫小宝。") is None
