"""
日志工具 — 统一的 rich 格式化日志配置。

=== 为什么需要日志？===
开发时你需要知道代码运行到哪了、出了什么问题。
print() 太简陋（没有时间、没有级别），而且无法控制输出量。
logging 模块提供分级别、带时间、可控制开关的日志系统。

=== 日志级别 ===
从低到高：
- DEBUG: 最详细，调试时用（开发时看）
- INFO: 重要信息（正常运行时看）
- WARNING: 警告（可能有问题但能继续运行）
- ERROR: 出错了（需要关注）
- CRITICAL: 严重错误（系统可能要崩了）

=== rich 库 ===
rich 让终端输出变得漂亮：彩色文字、进度条、表格等。
RichHandler 是 rich 的日志处理器，让日志输出带颜色和格式化。
"""

from __future__ import annotations

# logging 是 Python 标准库的日志模块
import logging

# sys 用于获取标准错误流（stderr），日志默认输出到 stderr
import sys


def get_logger(name: str) -> logging.Logger:
    """
    获取统一配置的 logger。

    使用 rich 格式化输出，支持 DEBUG/INFO/WARNING/ERROR。

    === 为什么用 logger.handlers 判断？===
    Python 的 getLogger(name) 如果同名 logger 已存在就返回已有的。
    如果重复添加 handler，同一行日志会输出多次。
    所以先检查 handlers 列表，只有为空时才添加。

    Args:
        name: logger 名称，通常传 __name__（当前模块名）。

    Returns:
        配置好的 Logger 实例。
    """
    # getLogger(name) 获取（或创建）一个命名 logger
    logger = logging.getLogger(name)

    # 只有还没有 handler 时才添加（防止重复添加导致日志重复输出）
    if not logger.handlers:
        try:
            # 尝试导入 rich（已安装在依赖中）
            from rich.logging import RichHandler

            # RichHandler 让日志输出带颜色和格式
            handler = RichHandler(
                show_time=True,          # 显示时间
                show_path=False,         # 不显示文件路径（太长）
                rich_tracebacks=True,    # 异常堆栈也用 rich 格式化
            )
            # RichHandler 自带格式，只需简单指定消息格式
            fmt = logging.Formatter("%(message)s")

        except ImportError:
            # 如果没装 rich，降级为标准格式
            handler = logging.StreamHandler(sys.stderr)
            fmt = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            )

        # 把格式器设置到处理器
        handler.setFormatter(fmt)
        # 把处理器添加到 logger
        logger.addHandler(handler)
        # 设置最低输出级别为 DEBUG（输出所有级别的日志）
        logger.setLevel(logging.DEBUG)
        # 不向父 logger 传播（防止重复输出）
        logger.propagate = False

    return logger
