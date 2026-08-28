"""
LLM 响应缓存 — 相同输入不重复调用 API。

=== 缓存原理 ===
把 messages（发给 LLM 的消息列表）转成一个 hash 值（唯一标识），
然后以 hash 为 key 存储 LLM 的回复。
下次相同的 messages 来了，先查缓存，命中就直接返回。

=== TTL ===
TTL = Time To Live（存活时间）。
缓存不是永久有效的，超过 TTL 就视为过期，需要重新调用 API。
因为 LLM 的回复可能有一定随机性，旧的缓存不一定还合适。

=== LRU ===
LRU = Least Recently Used（最近最少使用）。
当缓存满了时，删掉最久没用的那条，腾位置给新的。
"""

from __future__ import annotations

# hashlib 提供哈希算法（SHA-256），用于生成缓存 key
import hashlib

# time 用于获取当前时间戳，判断缓存是否过期
import time

from dataclasses import dataclass, field


@dataclass
class _CacheEntry:
    """
    缓存条目 — 存储一条 LLM 回复。

    Attributes:
        content: LLM 回复的文本内容。
        timestamp: 存入缓存时的时间戳（从 1970 年到现在的秒数）。
        ttl: 这条缓存的存活时间（秒）。
    """
    content: str
    timestamp: float
    ttl: float


@dataclass
class ResponseCache:
    """
    基于内存的 LLM 响应缓存。

    === 完整流程 ===
    1. AgentLoop 调用 LLM 前，先调 cache.get(messages) 查缓存
    2. 如果命中（返回非 None），直接用缓存的回复
    3. 如果没命中，调 LLM API，然后把结果存入 cache.set()
    4. 下次相同的 messages 来了，就能命中缓存

    Attributes:
        ttl: 缓存存活时间（秒），0 表示永不过期。默认 3600 秒 = 1 小时。
        max_size: 最大缓存条目数。默认 1000 条。
    """

    ttl: float = 3600.0
    max_size: int = 1000

    # 内部缓存字典：key 是 hash 值，value 是 _CacheEntry
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)

    def get(self, messages: list[dict]) -> str | None:
        """
        查缓存。

        Args:
            messages: 发给 LLM 的消息列表。

        Returns:
            如果缓存命中且未过期，返回缓存的回复文本。
            否则返回 None（表示需要调用 API）。
        """
        # 把 messages 转成 hash key
        key = self._make_key(messages)
        entry = self._cache.get(key)

        # 没找到缓存
        if entry is None:
            return None

        # 检查是否过期
        # time.time() 返回当前时间戳（秒）
        # 当前时间 - 存入时间 > TTL → 已过期
        if self.ttl > 0 and time.time() - entry.timestamp > self.ttl:
            # 过期了，删除这条缓存
            del self._cache[key]
            return None

        # 缓存命中且未过期，返回内容
        return entry.content

    def set(self, messages: list[dict], content: str) -> None:
        """
        写缓存。

        如果缓存已满，用简单的 LRU 策略删除最旧的一条。

        Args:
            messages: 消息列表（用于生成 key）。
            content: LLM 回复文本。
        """
        # 缓存满了，淘汰最旧的一条
        if len(self._cache) >= self.max_size:
            # min() 找出 timestamp 最小（最早存入）的 key
            # lambda k: self._cache[k].timestamp 返回每个条目的时间戳
            oldest = min(self._cache, key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest]

        # 生成 key 并存入缓存
        key = self._make_key(messages)
        self._cache[key] = _CacheEntry(
            content=content,
            timestamp=time.time(),  # 当前时间
            ttl=self.ttl,
        )

    def clear(self) -> None:
        """清空所有缓存。"""
        self._cache.clear()

    @staticmethod
    def _make_key(messages: list[dict]) -> str:
        """
        将 messages 序列化为缓存 key。

        把消息列表转成一个唯一的字符串，然后用 SHA-256 生成 hash。
        相同的消息列表会生成相同的 hash，所以能命中缓存。

        Args:
            messages: 消息列表。

        Returns:
            64 字符的 SHA-256 hex 字符串。
        """
        # 把 messages 转成字符串
        # sorted 按 content 排序，确保消息顺序不影响 key 生成
        raw = str(sorted(messages, key=lambda m: m.get("content", "")))
        # SHA-256 哈希：把任意长度的字符串转成 64 字符的固定长度 hex
        # 相同输入一定产生相同输出
        # 不同输入几乎不可能产生相同输出（碰撞概率极低）
        return hashlib.sha256(raw.encode()).hexdigest()
