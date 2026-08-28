"""
文本切块 — 把长文档切成适合检索的小段。

=== 为什么要切块？===
整本说明书塞进一次检索，噪声太大：一段里既有年假又有茶水间密码，
问「年假」时会把不相关的字也带给 LLM。
切成大约 400 字的段落，检索时只把最相关的几段交给模型。

=== 怎么切？===
1. 先按空行（Markdown 自然段）切开
2. 某一段仍然太长，再按句号切开，尽量在句子边界结束
3. 一句话本身就超过上限，再按固定字数硬切（带一点重叠，避免半句话丢失上下文）
"""

from __future__ import annotations

import re

# 一段理想长度（字符数；中文大约等于字数）
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
        overlap: 只有走「硬切窗口」时才用到。
    """
    raw = (text or "").strip()
    if not raw:
        return []

    # \n\s*\n：两个换行之间可以夹空白，对应 Markdown 空行分段
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    pieces: list[str] = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            pieces.append(para)
            continue
        pieces.extend(_split_long(para, chunk_size, overlap))
    return pieces


def _split_long(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    自然段太长时：先按句子拼，拼不下再新开一段。

    (?<=[。！？.!?]) 是「零宽后顾」：在句号后面切开，句号本身留在前一句。
    """
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", text) if s.strip()]
    if not sentences:
        return _window(text, chunk_size, overlap)

    out: list[str] = []
    buf = ""  # 正在拼的这一段
    for sent in sentences:
        # 单句就已经超长（很少见），只能硬切
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
            # 加上这句会超，先把已有的存下来，这句放到下一段
            out.append(buf)
            buf = sent
    if buf:
        out.append(buf)
    return out


def _window(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    固定窗口滑动切分。

    step = chunk_size - overlap：下一块的起点往回叠 overlap 个字。
    例如 size=400、overlap=40，则每步前进 360 字。
    """
    step = max(chunk_size - overlap, 1)
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size].strip())
        start += step
    return [c for c in chunks if c]
