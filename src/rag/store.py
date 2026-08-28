"""
向量知识库 — 存文档片段，按「问句向量」找出最像的几段。

=== 它在 RAG 里扮演哪一步？===
灌入：文字 → 切块 → embed() → 存进本文件的 chunks 列表
检索：问句 → embed() → 和每一段算余弦相似度 → 取分数最高的 k 段

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
    """
    检索命中的一段文字。

    score：余弦相似度，越大越相关（大约在 0～1，教学哈希很少到负数）。
    source：来源标记，例如 leave-policy.md，方便你对照原文。
    """

    id: str
    text: str
    source: str
    score: float


@dataclass
class VectorStore:
    """
    内存 + JSON 文件的向量库。

    persist_path:
        - 传目录路径：索引写到 该目录/index.json，重启不丢
        - 传 None：只放内存，进程结束就没了（单元测试常用，避免污染磁盘）
    """

    persist_path: str | None = None
    # field(default_factory=list) 避免「所有实例共享同一个列表」的坑
    chunks: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """dataclass 在 __init__ 之后自动调用。有持久化路径就建目录并尝试加载。"""
        if self.persist_path:
            Path(self.persist_path).mkdir(parents=True, exist_ok=True)
            self._load()

    def _index_file(self) -> Path:
        """索引文件的完整路径。"""
        return Path(self.persist_path) / "index.json"

    def _load(self) -> None:
        """从磁盘读回 chunks。文件坏了就当空库，不把服务弄挂。"""
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
        """把内存里的 chunks 整份写回 JSON。ensure_ascii=False 才能正确保存中文。"""
        if not self.persist_path:
            return
        path = self._index_file()
        path.write_text(
            json.dumps({"chunks": self.chunks}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, texts: list[str], source: str = "manual") -> list[str]:
        """
        写入若干文本片段：每段立刻算向量，再追加到列表。

        source 会印在检索结果里，也用于 delete_by_source（同一文件重新灌入时先删旧的）。

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
        """
        删掉某个来源的全部片段。

        重新灌入 leave-policy.md 前先调用，避免新旧两版制度同时存在、检索打架。
        """
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.get("source") != source]
        removed = before - len(self.chunks)
        if removed:
            self._save()
        return removed

    def query(self, text: str, top_k: int = 3) -> list[RetrievedChunk]:
        """
        找出和问句最像的 top_k 段。

        做法很朴素：问句 embed 一次，和库里每一段算余弦，再排序。
        教学库通常只有几十段，O(n) 扫描完全够用。空库或空查询返回 []。
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
        # reverse=True：分数从高到低
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[: max(top_k, 1)]

    def count(self) -> int:
        """当前库里有多少段，给 /health 的 knowledge_chunks 用。"""
        return len(self.chunks)


# =====================================================================
# 进程内单例
# HTTP POST /knowledge 灌入的文档，必须和 Agent 的 retrieve 用同一份库。
# 如果每次 new VectorStore()，灌入的内容 Agent 看不见。
# =====================================================================
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """
    拿到全局知识库。第一次调用时：
    1. 从 JSON 加载已有索引（上次跑服务留下的）
    2. 如果还是空的，把 data/knowledge/ 下的 md/txt 灌进去

    ingest_directory 写在函数里面 import，避免 store ↔ ingest 模块顶层循环引用。
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
    """
    测试用：把全局单例换成临时库，或传 None 清空。

    测完务必在 finally 里 reset_vector_store(None)，否则后面的测试会互相污染。
    """
    global _store
    _store = store
