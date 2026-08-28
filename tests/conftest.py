"""
pytest 全局 fixtures。

=== 什么是 fixture？===
fixture 是 pytest 的"准备工具"：在测试运行前准备好环境，
测试结束后清理。

比如测试异步代码需要 event loop，fixture 负责创建和销毁。

=== 什么是 conftest.py？===
conftest.py 是 pytest 的特殊文件，里面的 fixture 对所有测试自动可用，
不需要 import。pytest 会自动发现并加载它。
"""

import asyncio
from collections.abc import Generator

import pytest


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    提供一个 fresh event loop。

    yield 是关键：
    - yield 之前：创建 event loop（准备工作）
    - yield 返回：测试函数使用这个 loop
    - yield 之后：测试结束，关闭 loop（清理工作）

    这就是"setup → test → teardown"模式。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
