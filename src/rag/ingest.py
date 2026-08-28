"""
灌入知识 — 把文件或一段文字切块后写入向量库。

=== 典型用法 ===
命令行 / 启动时：ingest_directory("data/knowledge")
HTTP POST /knowledge：ingest_text(用户提交的正文, source="api")
"""

from __future__ import annotations

from pathlib import Path

from src.rag.chunker import chunk_text
from src.rag.store import VectorStore, get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)

_TEXT_SUFFIXES = {".md", ".txt"}


def ingest_text(
    text: str,
    source: str = "manual",
    *,
    store: VectorStore | None = None,
    replace: bool = True,
) -> int:
    """
    把一段文字写入知识库。

    Args:
        text: 原始文本。
        source: 来源标记，检索结果里会显示，也用于覆盖更新。
        store: 不传则用全局单例。
        replace: True 时先删掉该 source 的旧片段，避免重复。

    Returns:
        新写入的片段数量。
    """
    db = store if store is not None else get_vector_store()
    if replace:
        db.delete_by_source(source)
    pieces = chunk_text(text)
    ids = db.add(pieces, source=source)
    return len(ids)


def ingest_directory(
    directory: str,
    *,
    store: VectorStore | None = None,
) -> int:
    """
    把目录里所有 .md / .txt 灌进知识库。

    找不到目录就返回 0，不报错（没放知识文件时服务仍能启动）。
    """
    root = Path(directory)
    if not root.is_dir():
        logger.info("Knowledge dir missing, skip ingest: %s", directory)
        return 0
    db = store if store is not None else get_vector_store()
    total = 0
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        if not path.is_file():
            continue
        # 目录说明不是「业务知识」，跳过避免污染检索
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        total += ingest_text(text, source=path.name, store=db, replace=True)
    return total
