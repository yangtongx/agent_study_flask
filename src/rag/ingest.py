"""
灌入知识 — 把文件或一段文字切块后写入向量库。

=== 典型用法 ===
启动时空库：ingest_directory("data/knowledge")  （get_vector_store 里会自动调）
HTTP POST /knowledge：ingest_text(用户提交的正文, source="api")

=== 流水线 ===
原文 → chunk_text 切成小段 → VectorStore.add 算向量并保存
"""

from __future__ import annotations

from pathlib import Path

from src.rag.chunker import chunk_text
from src.rag.store import VectorStore, get_vector_store
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 只灌入纯文本。PDF / Word 需要额外解析，教学项目先不做。
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
        text: 原始文本（可以很长，内部会切块）。
        source: 来源标记，检索结果里会显示，也用于覆盖更新。
        store: 不传则用全局单例（和 Agent 检索同一份）。
        replace: True 时先删掉该 source 的旧片段，避免同一文件灌两次变成重复命中。

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

    rglob("*")：包括子文件夹。
    找不到目录就返回 0，不报错（没放知识文件时服务仍能启动）。
    README.md 是给人看的目录说明，不是业务知识，跳过以免污染检索。
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
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        # source 用文件名（leave-policy.md），检索结果里更好认
        total += ingest_text(text, source=path.name, store=db, replace=True)
    return total
