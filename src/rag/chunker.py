"""
文本切块 — 把长文档切成适合检索的小段。

=== 为什么要切块？===
整本说明书塞进一次检索，噪声太大。
切成 200～400 字的段落，检索时只把最相关的几段交给 LLM。

=== 怎么切？===
1. 先按空行（Markdown 自然段）切开
2. 某一段仍然太长，再按句号 / 换行切开
3. 仍然太长就按固定字数硬切（带一点重叠，避免一句话被从中间砍断）
"""

from __future__ import annotations

import re

# 一段理想长度（字符数，中文约等于字数）
DEFAULT_CHUNK_SIZE = 400
# 硬切时和上一段重叠多少字，减轻「半句话」问题
DEFAULT_OVERLAP = 40


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """
    把 text 切成若干非空小段。

    Args:
        text: 原始文档。
        chunk_size: 每段目标上限。
        overlap: 硬切时的重叠字数。
    """
    raw = (text or "").strip()
    if not raw:
        return []

    # 按空行分成自然段
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    pieces: list[str] = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            pieces.append(para)
            continue
        pieces.extend(_split_long(para, chunk_size, overlap))
    return pieces


def _split_long(text: str, chunk_size: int, overlap: int) -> list[str]:
    """先按句子切，句子还是太长再按窗口硬切。"""
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", text) if s.strip()]
    if not sentences:
        return _window(text, chunk_size, overlap)

    out: list[str] = []
    buf = ""
    for sent in sentences:
        if len(sent) > chunk_size:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_window(sent, chunk_size, overlap))
            continue
        candidate = f"{buf}\n{sent}".strip() if buf else sent
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            out.append(buf)
            buf = sent
    if buf:
        out.append(buf)
    return out


def _window(text: str, chunk_size: int, overlap: int) -> list[str]:
    """固定窗口滑动切分。"""
    step = max(chunk_size - overlap, 1)
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size].strip())
        start += step
    return [c for c in chunks if c]
