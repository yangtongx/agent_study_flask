"""
RAG 模块 — Retrieval-Augmented Generation（检索增强生成）。

=== 一句话 ===
先从知识库找出相关段落，再让 LLM 根据这些段落回答。
这样 Agent 可以「翻笔记」，而不是全靠模型脑子里的训练数据。

=== 四个零件 ===
- embeddings.py  把文字变成向量（一串数字）
- chunker.py     把长文切成小段
- store.py       存向量、按相似度找出最像的几段
- ingest.py      把文件 / HTTP 传来的文本灌进知识库
"""

from src.rag.ingest import ingest_directory, ingest_text
from src.rag.store import VectorStore, get_vector_store

__all__ = [
    "VectorStore",
    "get_vector_store",
    "ingest_text",
    "ingest_directory",
]
