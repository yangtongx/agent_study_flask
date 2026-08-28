"""
长期记忆 — 接上 RAG 向量库。

以前是 stub（只打日志、返回空列表）。
现在 store / retrieve 转到 src.rag.VectorStore：
- 对话里的「知识」和 HTTP 灌入的文档，都在同一份索引里
- 仍然保持原来的方法名，MemoryManager 不用改调用方式
"""

from __future__ import annotations

from src.rag.store import VectorStore, get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LongTermMemory:
    """
    长期记忆 — 基于向量相似度检索的知识。

    persist_path 仍接收（兼容 MemoryManager 旧参数），
    真正读写走全局 VectorStore，这样 /knowledge 灌入的文档 Agent 立刻能搜到。
    """

    def __init__(self, persist_path: str | None = None) -> None:
        self.persist_path = persist_path
        self._store: VectorStore | None = None
        logger.info("LongTermMemory initialized (RAG backend)")

    def _db(self) -> VectorStore:
        return self._store if self._store is not None else get_vector_store()

    def store(self, content: str, metadata: dict | None = None) -> str:
        """
        存储一条记忆。

        metadata.source 会当成来源标记；没有则用 long_term。
        """
        source = "long_term"
        if metadata and metadata.get("source"):
            source = str(metadata["source"])
        ids = self._db().add([content], source=source)
        return ids[0] if ids else ""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        检索相关记忆。

        Returns:
            [{content, score, source, id}, ...]
        """
        hits = self._db().query(query, top_k=top_k)
        return [
            {
                "id": h.id,
                "content": h.text,
                "source": h.source,
                "score": h.score,
            }
            for h in hits
        ]

    def forget(self, memory_id: str) -> bool:
        """按 id 删一条。找不到返回 False。"""
        db = self._db()
        before = len(db.chunks)
        db.chunks = [c for c in db.chunks if c.get("id") != memory_id]
        removed = before != len(db.chunks)
        if removed:
            db._save()
        return removed
