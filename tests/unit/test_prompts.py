"""提示词模板加载测试。"""

from langchain_core.prompts import ChatPromptTemplate

from src.prompts.loader import (
    build_chat_messages,
    build_system_prompt,
    build_task_prompt,
    get_chat_prompt_template,
    load_prompt,
)
from src.tools.calculator import CalculatorTool


def test_load_prompt_reads_markdown():
    """能从 src/prompts/ 读到模板文件。"""
    text = load_prompt("system.md")
    assert "小宝" in text
    assert "{tool_descriptions}" in text


def test_chat_prompt_is_from_messages():
    """消息结构必须来自 ChatPromptTemplate.from_messages。"""
    prompt = get_chat_prompt_template()
    assert isinstance(prompt, ChatPromptTemplate)
    assert "tool_descriptions" in prompt.input_variables
    assert "user_input" in prompt.input_variables


def test_build_system_prompt_injects_tools_and_examples():
    """系统提示应注入工具描述，并拼上 few-shot 示例。"""
    tool = CalculatorTool()
    tool_desc = f"  - {tool.name}: {tool.description}"
    prompt = build_system_prompt(tool_desc)

    assert "你是 小宝" in prompt
    assert "calculator" in prompt
    assert "{tool_descriptions}" not in prompt
    assert "Action[calculator]" in prompt
    assert "Final Answer" in prompt
    assert "Action[fetch]" in prompt
    assert "核实" in prompt


def test_system_prompt_search_then_fetch_and_skip_identity_search():
    """问身份不要搜；查资料要搜完再 fetch；算术走计算器。"""
    text = load_prompt("system.md")
    assert "不要调用 web_search 或 fetch" in text
    assert "再 Action[fetch]" in text
    assert "必须用 calculator" in text
    assert "用户提问的语言" in text

    examples = load_prompt("examples.md")
    assert "不需要搜索" in examples
    assert "Action[web_search]" in examples
    assert "Action[fetch](https://www.python.org/downloads/)" in examples
    assert "直接 fetch，不必先搜" in examples


def test_build_task_prompt_wraps_user_input():
    """当前用户输入走 task.md，而不是裸字符串。"""
    rendered = build_task_prompt("你叫什么")
    assert "你叫什么" in rendered
    assert "{user_input}" not in rendered


def test_build_chat_messages_inserts_history():
    """history 应插在 system 和当前用户消息之间，role 要转成 OpenAI 格式。"""
    messages = build_chat_messages(
        tool_descriptions="  - calculator: math",
        history=[
            {"role": "user", "content": "上一句"},
            {"role": "assistant", "content": "上一答"},
        ],
        user_input="你叫什么",
    )

    assert messages[0]["role"] == "system"
    assert "calculator" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "上一句"}
    assert messages[2] == {"role": "assistant", "content": "上一答"}
    assert messages[-1]["role"] == "user"
    assert "你叫什么" in messages[-1]["content"]
    assert "用户输入" in messages[-1]["content"]
