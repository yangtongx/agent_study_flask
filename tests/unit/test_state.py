"""LangGraph State 单元测试。"""

from typing import get_args, get_origin, get_type_hints

from src.core.state import AgentState, append_messages


def test_append_messages_concatenates_instead_of_overwrite():
    """reducer 必须拼接：这就是 State 里 messages 不会丢历史的原因。"""
    existing = [{"role": "user", "content": "你叫什么"}]
    incoming = [{"role": "assistant", "content": "我叫 ReactAgent"}]
    merged = append_messages(existing, incoming)
    assert merged == existing + incoming
    # 原列表不应被原地改掉
    assert existing == [{"role": "user", "content": "你叫什么"}]


def test_agent_state_messages_use_append_reducer():
    """AgentState.messages 必须 Annotated 上 append_messages。"""
    hints = get_type_hints(AgentState, include_extras=True)
    annotation = hints["messages"]
    assert get_origin(annotation) is not None
    args = get_args(annotation)
    assert append_messages in args
