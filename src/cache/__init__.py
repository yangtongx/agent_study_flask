"""
Cache 模块 — LLM 响应缓存。

=== 为什么需要缓存？===
调用 LLM API 每次都要花钱（按 token 计费），
而且有网络延迟（几百毫秒到几秒）。

如果用户问了相同的问题，可以直接用之前缓存的回复，
不用再次调用 API —— 省钱、省时间。
"""

from src.cache.response_cache import ResponseCache

__all__ = ["ResponseCache"]
