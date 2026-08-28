"""
提示词模板加载。

=== 为什么用 ChatPromptTemplate.from_messages？===
发给 LLM 的不是一整段字符串，而是一组带 role 的消息：
    system（人设 + 工具 + few-shot）
    ...history（以前的 user / assistant）
    human（当前这一轮，来自 task.md）

LangChain 的 ChatPromptTemplate 就是专门拼这种消息列表的。
我们只用它来「组装 messages」，ReAct 循环和 HTTP 调模型仍然手写，
不会变成 LangChain Agent。
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 本文件所在目录就是模板目录：system.md / examples.md / task.md / retry.md
_PROMPT_DIR = Path(__file__).resolve().parent

# OpenAI Chat Completions 用 user/assistant/system；
# LangChain 消息类型是 human/ai/system。两边要互相转。
_LC_TO_OPENAI_ROLE = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
}


def load_prompt(name: str) -> str:
    """
    读取 src/prompts/ 下的模板文件。

    Args:
        name: 文件名，例如 "system.md"。

    Returns:
        文件全文（去掉首尾空白）。
    """
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8").strip()


def get_chat_prompt_template() -> ChatPromptTemplate:
    """
    用 ChatPromptTemplate.from_messages 声明消息结构。

    占位符：
        {tool_descriptions}  ← system.md
        {history}            ← MessagesPlaceholder，插入历史消息
        {user_input}         ← task.md
    """
    system_template = load_prompt("system.md") + "\n\n" + load_prompt("examples.md")
    return ChatPromptTemplate.from_messages(
        [
            ("system", system_template),
            MessagesPlaceholder("history", optional=True),
            ("human", load_prompt("task.md")),
        ]
    )


def _dicts_to_lc(history: list[dict]) -> list[BaseMessage]:
    """把记忆里的 OpenAI dict 转成 LangChain Message，才能塞进 MessagesPlaceholder。"""
    converted: list[BaseMessage] = []
    for item in history:
        role = item.get("role", "user")
        content = str(item.get("content", ""))
        if role == "assistant":
            converted.append(AIMessage(content=content))
        elif role == "system":
            converted.append(SystemMessage(content=content))
        else:
            converted.append(HumanMessage(content=content))
    return converted


def _lc_to_dicts(messages: list[BaseMessage]) -> list[dict]:
    """把 LangChain Message 转回 OpenAI dict，交给现有的 httpx 客户端。"""
    result: list[dict] = []
    for message in messages:
        role = _LC_TO_OPENAI_ROLE.get(message.type, "user")
        content = message.content
        if not isinstance(content, str):
            content = str(content)
        result.append({"role": role, "content": content})
    return result


def build_chat_messages(
    tool_descriptions: str,
    history: list[dict],
    user_input: str,
) -> list[dict]:
    """
    渲染完整的 Chat Completions messages。

    Returns:
        [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    """
    prompt = get_chat_prompt_template()
    formatted = prompt.format_messages(
        tool_descriptions=tool_descriptions or "  （当前没有可用工具）",
        history=_dicts_to_lc(history),
        user_input=user_input,
    )
    return _lc_to_dicts(formatted)


def build_system_prompt(tool_descriptions: str) -> str:
    """渲染后的 system 文本（测试和调试用）。"""
    messages = build_chat_messages(tool_descriptions, history=[], user_input="")
    return messages[0]["content"]


def build_task_prompt(user_input: str) -> str:
    """渲染后的当前用户消息（测试和调试用）。"""
    messages = build_chat_messages("", history=[], user_input=user_input)
    return messages[-1]["content"]
