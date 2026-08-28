"""
API 模块 — 将 Agent 包装为 HTTP 服务。

=== 为什么需要这一层？===
其他业务系统（Java 后端、前端、其他 Python 服务）需要调用 Agent，
但它们不能直接 import Python 代码。
通过 HTTP API，任何能发 HTTP 请求的系统都能使用 Agent。

=== 技术选型 ===
Flask：轻量、资料多，适合学习 HTTP 服务怎么把 Agent 暴露出去。
内置开发服务器：python server.py 即可在本机 8000 端口访问。
"""

from src.api.routes import bp

__all__ = ["bp"]
