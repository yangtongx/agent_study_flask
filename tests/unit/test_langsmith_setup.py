"""LangSmith 环境变量拷贝：不访问 smith.langchain.com。"""

import os

from src.configs.settings import get_settings
from src.utils import langsmith_setup


def test_apply_langsmith_env_copies_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_test_not_real")
    monkeypatch.setenv("LANGSMITH_PROJECT", "unit-test-project")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "")
    get_settings.cache_clear()
    langsmith_setup._applied = False

    assert langsmith_setup.apply_langsmith_env() is True
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "unit-test-project"

    get_settings.cache_clear()
    langsmith_setup._applied = False
