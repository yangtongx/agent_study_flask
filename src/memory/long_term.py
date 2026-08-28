"""
长期记忆 — 接上 RAG 向量库。

=== 以前 vs 现在 ===
以前是 stub：store() 只打日志，retrieve() 永远返回空列表。
现在这两步都转到 src.rag.VectorStore：
- HTTP 灌入的文档、这里 store() 的句子，都在同一份索引里
- 方法名故意保持不变，MemoryManager.retrieve_knowledge() 不用改调用方式

=== 和短期记忆的差别 ===
短期记忆：最近几轮对话原文，按时间顺序（deque 窗口）。
长期记忆：制度 / 说明文档，按「意思相近」搜，不按时间。
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
        # 测试可把 _store 换成临时 VectorStore；默认走全局单例
        self._store: VectorStore | None = None
        logger.info("LongTermMemory initialized (RAG backend)")

    def _db(self) -> VectorStore:
        """实际用的那份知识库。"""
        return self._store if self._store is not None else get_vector_store()

    def store(self, content: str, metadata: dict | None = None) -> str:
        """
        存储一条记忆。

        metadata.source 会当成来源标记；没有则用 long_term。
        返回新片段的 id，找不到可写入的内容时返回空字符串。
        """
        source = "long_term"
        if metadata and metadata.get("source"):
            source = str(metadata["source"])
        ids = self._db().add([content], source=source)
        return ids[0] if ids else ""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        检索相关记忆。

        返回 list[dict] 而不是 RetrievedChunk：MemoryManager 更早约定了这个形状。
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
        """
        按 id 删一条。找不到返回 False。

        直接改 db.chunks 后调用 _save()，与 VectorStore 内部结构耦合，
        教学项目里这样最直观；以后若换 Chroma 再改成官方 delete API。
        """
        db = self._db()
        before = len(db.chunks)
        db.chunks = [c for c in db.chunks if c.get("id") != memory_id]
        removed = before != len(db.chunks)
        if removed:
            db._save()
        return removed
