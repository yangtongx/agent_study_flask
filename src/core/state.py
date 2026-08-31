"""
LangGraph State — 图里每个节点读写的那一份共享数据。

=== 为什么 State 是 LangGraph 里最重要的概念？===
没有 State，节点之间只能靠返回值硬传，图一复杂就乱。
有了 State：每个节点读当前快照，只返回「要改的字段」；
LangGraph 按 reducer 把增量合并回去，再交给下一个节点。

=== reducer 是什么？===
默认行为：后来的值覆盖旧值（last write wins）。
消息列表不能覆盖——否则上一轮 Observation 就丢了。
所以 messages 用 Annotated[..., append_messages]：节点只返回新增的几条，
合并函数负责拼到已有列表后面。

官方教程常用 langgraph.graph.message.add_messages（面向 LangChain BaseMessage）。
本项目的 LLM 客户端吃 OpenAI 的 {"role","content"} dict，所以自己写一个同思路的
append_messages，便于对照学习。
"""

from __future__ import annotations

from typing import Annotated, TypedDict


def append_messages(
    existing: list[dict] | None,
    incoming: list[dict] | None,
) -> list[dict]:
    """
    messages 字段的 reducer：拼接，不覆盖。

    节点必须只返回「这一步新产生的消息」，例如：
        return {"messages": [{"role": "assistant", "content": "..."}]}
    不要把 state["messages"] 全量再 return 一遍，否则会重复。
    """
    return list(existing or []) + list(incoming or [])


class AgentState(TypedDict):
    """
    ReAct 循环在图上跑时的共享状态。

    Attributes:
        messages: 发给 LLM 的完整对话（含 system / 历史 / 本轮 Thought-Action）。
        user_input: 用户原始问题，结束时写入记忆。
        iteration: 已经调用了多少次 LLM（对应原来的 for 循环下标）。
        last_response: 最近一次 LLM 原文，供解析 Action / Final Answer。
        final_answer: 有值就该结束；None 表示还要继续转。
    """

    messages: Annotated[list[dict], append_messages]
    user_input: str
    iteration: int
    last_response: str
    final_answer: str | None
