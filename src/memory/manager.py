"""
记忆管理器 — 调度短期/长期记忆 + PG 持久化，统一对外接口。

=== 改动说明 ===
新增 session_id 和 ChatHistoryRepo：
- 对话不仅存在内存里，还持久化到 PostgreSQL
- 服务重启后，按 session_id 从 PG 加载历史到内存
- 如果 PG 连不上，降级为纯内存模式（不影响基本运行）

=== 为什么保留内存？===
每次调用 LLM 都要从 PG 读历史有 IO 开销。
内存缓存最近对话窗口，PG 做持久化备份。
"""

from __future__ import annotations

import uuid

from src.configs.settings import get_settings
from src.database.chat_history import ChatHistoryRepo
from src.memory.long_term import LongTermMemory
from src.memory.short_term import ShortTermMemory
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """
    记忆调度中心。

    组合三层存储：
    1. 短期记忆（内存 deque）：快速访问最近对话
    2. PostgreSQL（持久化）：服务重启后历史不丢
    3. 长期记忆（向量库 stub）：语义检索（预留）

    Attributes:
        session_id: 当前会话 ID，用于区分不同对话。
    """

    def __init__(
        self,
        window_size: int | None = None,
        session_id: str | None = None,
    ) -> None:
        """
        初始化记忆管理器。

        Args:
            window_size: 短期记忆窗口大小。
            session_id: 会话 ID。None 时自动生成 UUID。
                        同一个 session_id 的对话会从 PG 加载历史。
        """
        settings = get_settings()

        # 会话 ID：区分不同对话
        self.session_id = session_id or str(uuid.uuid4())

        # 短期记忆（内存）
        self.short_term = ShortTermMemory(
            window_size=window_size or settings.agent_memory_window
        )

        # 长期记忆（向量库 stub）
        self.long_term = LongTermMemory(
            persist_path=settings.chroma_persist_path
        )

        # PG 持久化：尝试从数据库加载历史到内存
        self._pg_available = False
        self._load_from_pg()

        logger.info(
            "MemoryManager initialized (session=%s, window=%d, pg=%s)",
            self.session_id[:8], self.short_term.window_size, self._pg_available,
        )

    def _load_from_pg(self) -> None:
        """从 PG 加载历史对话到内存。"""
        try:
            history = ChatHistoryRepo.get_history(self.session_id)
            for msg in history:
                self.short_term.add(msg["role"], msg["content"])
            if history:
                logger.info("Loaded %d messages from PG", len(history))
            self._pg_available = True
        except Exception as e:
            logger.warning("PG unavailable, running in memory-only mode: %s", e)
            self._pg_available = False

    def add_message(self, role: str, content: str, iterations: int = 0) -> None:
        """
        添加对话消息。

        同时写入内存和 PG（如果可用）。

        Args:
            role: "user" 或 "assistant"。
            content: 消息内容。
            iterations: ReAct 循环次数（仅 assistant）。
        """
        # 写内存
        self.short_term.add(role, content)

        # 写 PG
        if self._pg_available:
            try:
                ChatHistoryRepo.save_message(
                    self.session_id, role, content, iterations,
                )
            except Exception as e:
                logger.error("Failed to save to PG: %s", e)

    def get_recent_history(self) -> list[dict]:
        """获取最近对话历史（从内存）。"""
        return self.short_term.get_all()

    def store_knowledge(self, content: str, metadata: dict | None = None) -> str:
        """存储长期知识。"""
        return self.long_term.store(content, metadata)

    def retrieve_knowledge(self, query: str, top_k: int = 5) -> list[dict]:
        """检索长期知识。"""
        return self.long_term.retrieve(query, top_k=top_k)

    def clear(self) -> None:
        """清空记忆（内存 + PG）。"""
        self.short_term.clear()
        if self._pg_available:
            try:
                ChatHistoryRepo.clear_session(self.session_id)
            except Exception as e:
                logger.error("Failed to clear PG history: %s", e)
        logger.info("Memory cleared (session=%s)", self.session_id[:8])
