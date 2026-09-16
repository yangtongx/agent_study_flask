"""
LangSmith 开关 — 把 .env 里的配置写进进程环境变量。

=== 为什么要这一步？===
LangGraph 看的是操作系统环境变量 LANGSMITH_TRACING / LANGSMITH_API_KEY，
不是 pydantic 的 Settings 对象。
本项目的密钥都写在 .env 里，pydantic 会读进 Settings，
但默认不会把「多余字段」再塞回 os.environ。
所以要手动拷一次，LangSmith 才能收到 perceive / decide / act 这些节点。

=== 在网页上看到什么？===
一条对话 = 一条 Trace。点进去能看到图：
    perceive → decide → act → decide → … → END
decide 里面还有 llm.chat；act 里面还有 tool.run。
"""

from __future__ import annotations

import os

from src.configs.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_applied = False


def hide_self(inputs: dict) -> dict:
    """不要把 self（里面有 API Key）上传到 LangSmith。"""
    out = {k: v for k, v in inputs.items() if k != "self"}
    obj = inputs.get("self")
    if obj is not None:
        model = getattr(obj, "model", None)
        if model:
            out["model"] = model
    return out


def llm_traceable(fn):
    """套在 OpenAIClient.chat 上：LangSmith 里显示为 LLM 节点。没装 langsmith 时原样返回。"""
    try:
        from langsmith import traceable
    except ImportError:
        return fn
    return traceable(run_type="llm", name="llm.chat", process_inputs=hide_self)(fn)


async def run_tool_traced(tool_name: str, args: str, runner) -> str:
    """跑工具，并在 LangSmith 里记一笔 tool 节点。"""
    try:
        from langsmith import traceable
    except ImportError:
        return str(await runner(args))

    @traceable(run_type="tool", name=tool_name)
    async def _inner(tool: str, arguments: str) -> str:
        return str(await runner(arguments))

    return await _inner(tool_name, args)


def apply_langsmith_env() -> bool:
    """
    按 Settings 打开或关掉 LangSmith tracing。

    Returns:
        True 表示已经打开（有 Key 且 tracing=true）。
    """
    global _applied
    settings = get_settings()
    tracing = bool(settings.langsmith_tracing)
    api_key = (settings.langsmith_api_key or "").strip()
    project = (settings.langsmith_project or "agent-study-flask").strip()
    endpoint = (settings.langsmith_endpoint or "").strip()

    if tracing and not api_key:
        logger.warning(
            "LANGSMITH_TRACING=true 但没填 LANGSMITH_API_KEY。"
            "到 https://smith.langchain.com/settings 建一把 Key，写进 .env。"
        )
        return False

    if tracing and api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGSMITH_API_KEY"] = api_key
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGSMITH_PROJECT"] = project
        os.environ["LANGCHAIN_PROJECT"] = project
        if endpoint:
            os.environ["LANGSMITH_ENDPOINT"] = endpoint
        if not _applied:
            logger.info("LangSmith tracing on, project=%s", project)
            _applied = True
        return True

    os.environ.setdefault("LANGSMITH_TRACING", "false")
    if not _applied:
        logger.info("LangSmith tracing off（.env 里 LANGSMITH_TRACING=true 才会上传）")
        _applied = True
    return False
