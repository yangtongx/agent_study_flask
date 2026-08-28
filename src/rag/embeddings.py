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

# hashlib：把任意字符串变成固定长度的「指纹」。同一输入永远得到同一输出。
import hashlib

# math.sqrt 用来算向量长度（L2 范数）
import math

# re：正则。这里用来丢掉标点，只留下中文、字母、数字。
import re

# 向量长度。越大越能区分不同词，也越占内存。64 对教学演示够用。
EMBED_DIM = 64

# [^\w\u4e00-\u9fff]+ 意思是：连续的「非字母数字、非汉字」都当成分隔符
# \u4e00-\u9fff 是常用汉字的 Unicode 范围
_KEEP = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _normalize(text: str) -> str:
    """
    清洗文本：去掉标点、英文转小写。

    这样「年假？」和「年假」会变成同一串字，检索不容易漏。
    text or ""：防止调用方传入 None。
    """
    return _KEEP.sub(" ", (text or "").lower()).strip()


def _ngrams(text: str) -> list[str]:
    """
    抽出 1-gram、2-gram、3-gram。

    n-gram = 连续 n 个字。例如「年假」：
        1-gram: 年、假
        2-gram: 年假
        3-gram: 字不够 3 个，跳过

    英文单词之间有空格，先 split 再对每个词切相邻组合。
    「年假」两个字如果只切 1-gram，问句「有几天」也对不上「年假」这个词本身，
    所以 2-gram / 3-gram 很重要。
    """
    parts = [p for p in text.split() if p]
    grams: list[str] = []
    for part in parts:
        chars = list(part)
        for n in (1, 2, 3):
            if len(chars) < n:
                continue
            # 滑动窗口：i 从 0 走到能放下 n 个字的最后一个位置
            for i in range(len(chars) - n + 1):
                grams.append("".join(chars[i : i + n]))
    return grams


def _bucket(gram: str) -> int:
    """
    把一个 n-gram 稳定地映射到 0～EMBED_DIM-1。

    md5 得到 16 进制字符串 → int(..., 16) 变成大整数 → 对 64 取余。
    「稳定」是指：同一个「年假」，每次都进同一个格子。
    """
    digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
    return int(digest, 16) % EMBED_DIM


def embed(text: str) -> list[float]:
    """
    把文本变成长度为 EMBED_DIM 的单位向量。

    步骤：
    1. 准备 64 个 0
    2. 每个 n-gram 落到某个格子，那个格子 +1（词出现越多，格子越大）
    3. 除以向量长度，变成「长度为 1」的单位向量

    空文本返回全 0：后面和任何向量点积都是 0，不会误当成「很相关」。
    """
    vec = [0.0] * EMBED_DIM
    grams = _ngrams(_normalize(text))
    if not grams:
        return vec
    for g in grams:
        vec[_bucket(g)] += 1.0
    # L2 归一化：每个分量除以 sqrt(平方和)。归一化后，点积 = 余弦相似度。
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """
    两个等长向量的点积（调用方应传入已经归一化的向量）。

    zip(..., strict=True)：长度不一致会立刻报错，避免默默算错。
    """
    return sum(x * y for x, y in zip(a, b, strict=True))
