"""
简易向量化 — 把一段文字变成一串数字（向量）。

=== 什么是 embedding？===
计算机不会「读懂」中文，但会算数字。
embedding 的意思是：用一套规则，把「年假有几天」映射成例如 64 个小数。
意思相近的句子，映射出来的数字也会比较接近。

=== 为什么不用网上的大 embedding 模型？===
教学项目优先「能跑、能看懂、不下载几百 MB」。
这里用「字符 n-gram 哈希」：
1. 把文本切成相邻 1～3 个字的片段（n-gram）
2. 每个片段哈希到 0～63 的某个格子，那个格子 +1
3. 最后把这 64 个数除以长度，变成单位向量

这不是工业级语义模型（「狗」和「犬」不一定很近），
但对关键词重合的中文文档（请假制度、项目说明）足够做演示。
以后要换真模型，只改这一个文件即可。

=== 什么是余弦相似度？===
两个单位向量做点积，结果在 -1～1：
越接近 1，方向越像，我们认为「语义越相关」。
"""

from __future__ import annotations

import hashlib
import math
import re

# 向量长度。越大越能区分不同词，也越占内存。64 对教学演示够用。
EMBED_DIM = 64

# 只保留中文、字母、数字；其它符号当分隔符
_KEEP = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _normalize(text: str) -> str:
    """去掉标点、压成小写，方便「年假？」和「年假」对上。"""
    return _KEEP.sub(" ", (text or "").lower()).strip()


def _ngrams(text: str) -> list[str]:
    """
    抽出 1-gram、2-gram、3-gram。

    例如「年假」→ ['年', '假', '年假']
    英文单词之间有空格，按 token 再切相邻组合。
    """
    parts = [p for p in text.split() if p]
    grams: list[str] = []
    for part in parts:
        chars = list(part)
        for n in (1, 2, 3):
            if len(chars) < n:
                continue
            for i in range(len(chars) - n + 1):
                grams.append("".join(chars[i : i + n]))
    return grams


def _bucket(gram: str) -> int:
    """把一个 n-gram 稳定地映射到 0～EMBED_DIM-1。"""
    digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
    return int(digest, 16) % EMBED_DIM


def embed(text: str) -> list[float]:
    """
    把文本变成长度为 EMBED_DIM 的单位向量。

    空文本返回全 0（检索时相似度会是 0，不会误伤）。
    """
    vec = [0.0] * EMBED_DIM
    grams = _ngrams(_normalize(text))
    if not grams:
        return vec
    for g in grams:
        vec[_bucket(g)] += 1.0
    # L2 归一化：除以根号(平方和)，之后点积就是余弦相似度
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """两个等长向量的点积（输入应已归一化）。"""
    return sum(x * y for x, y in zip(a, b, strict=True))
