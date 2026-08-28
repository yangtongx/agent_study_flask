"""
向量知识库 — 存文档片段，按「问句向量」找出最像的几段。

=== 和 ChromaDB 的关系 ===
settings 里还留着 CHROMA_PERSIST_PATH，那是更早的预留。
本教学实现不用 Chroma（免下载 embedding 模型），把索引存成 JSON：
    data/rag/index.json

每条记录：id、text、source、vector。
进程重启后只要文件还在，知识库就还在。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.configs.settings import get_settings
from src.rag.embeddings import cosine, embed
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievedChunk:
    """检索命中的一段文字。"""

    id: str
    text: str
    source: str
    score: float  # 余弦相似度，越大越相关


@dataclass
class VectorStore:
    """
    内存 + JSON 文件的向量库。

    persist_path: 目录。索引文件是这个目录下的 index.json。
    传空字符串则只放内存，进程结束就没了（测试常用）。
    """

    persist_path: str | None = None
    chunks: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.persist_path:
            Path(self.persist_path).mkdir(parents=True, exist_ok=True)
            self._load()

    def _index_file(self) -> Path:
        return Path(self.persist_path) / "index.json"

    def _load(self) -> None:
        path = self._index_file()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.chunks = list(data.get("chunks") or [])
            logger.info("RAG index loaded: %d chunks from %s", len(self.chunks), path)
        except Exception as e:
            logger.warning("Failed to load RAG index, starting empty: %s", e)
            self.chunks = []

    def _save(self) -> None:
        if not self.persist_path:
            return
        path = self._index_file()
        path.write_text(
            json.dumps({"chunks": self.chunks}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, texts: list[str], source: str = "manual") -> list[str]:
        """
        写入若干文本片段。

        Returns:
            新片段的 id 列表。
        """
        ids: list[str] = []
        for text in texts:
            text = (text or "").strip()
            if not text:
                continue
            chunk_id = uuid.uuid4().hex[:12]
            self.chunks.append(
                {
                    "id": chunk_id,
                    "text": text,
                    "source": source,
                    "vector": embed(text),
                }
            )
            ids.append(chunk_id)
        if ids:
            self._save()
            logger.info("RAG stored %d chunks (source=%s, total=%d)", len(ids), source, len(self.chunks))
        return ids

    def delete_by_source(self, source: str) -> int:
        """删掉某个来源的全部片段（重新灌入同一文件前调用）。"""
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.get("source") != source]
        removed = before - len(self.chunks)
        if removed:
            self._save()
        return removed

    def query(self, text: str, top_k: int = 3) -> list[RetrievedChunk]:
        """
        找出和 query 最像的 top_k 段。

        空库或空查询返回 []。
        """
        q = (text or "").strip()
        if not q or not self.chunks:
            return []
        qv = embed(q)
        scored: list[RetrievedChunk] = []
        for c in self.chunks:
            score = cosine(qv, c["vector"])
            scored.append(
                RetrievedChunk(
                    id=c["id"],
                    text=c["text"],
                    source=c.get("source") or "",
                    score=score,
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[: max(top_k, 1)]

    def count(self) -> int:
        return len(self.chunks)


# 进程内单例：HTTP 灌入的知识和 Agent 检索必须是同一份库
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """
    拿到全局知识库。第一次调用时：
    1. 从 JSON 加载已有索引
    2. 如果还是空的，把 data/knowledge/ 下的 md/txt 灌进去
    """
    global _store
    if _store is None:
        settings = get_settings()
        _store = VectorStore(persist_path=settings.rag_persist_path)
        if _store.count() == 0:
            from src.rag.ingest import ingest_directory

            n = ingest_directory(settings.rag_knowledge_dir, store=_store)
            logger.info("Seeded knowledge dir: %d chunks", n)
    return _store


def reset_vector_store(store: VectorStore | None = None) -> None:
    """测试用：换成临时库，或清空单例。"""
    global _store
    _store = store
