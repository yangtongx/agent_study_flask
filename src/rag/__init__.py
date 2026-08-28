"""
RAG 模块 — Retrieval-Augmented Generation（检索增强生成）。

=== 一句话 ===
先从知识库找出相关段落，再让 LLM 根据这些段落回答。
这样 Agent 可以「翻笔记」，而不是全靠模型脑子里的训练数据。

=== 建议阅读顺序 ===
先读本文件了解全貌，再按「切块 → 向量 → 存储 → 灌入」看四个零件。
Agent 真正动手的入口是 src/tools/retrieve.py。
"""

from src.rag.ingest import ingest_directory, ingest_text
from src.rag.store import VectorStore, get_vector_store

__all__ = [
    "VectorStore",
    "get_vector_store",
    "ingest_text",
    "ingest_directory",
]
