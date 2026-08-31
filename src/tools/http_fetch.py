"""
HTTP 拉取 — 给搜索和 fetch 工具共用。

=== 搜索和 fetch 差在哪？===
搜索引擎结果页经常只有标题和跳转链接。
要读到实质内容，必须再 GET 一次真实文章 URL，把 HTML 收成纯文本。
这就是这里的 fetch：不是浏览器里的 fetch()，就是一次普通 HTTP GET。

搜索工具会偷偷对前几条结果调用 fetch_text()，补一段正文摘要。
fetch 工具则把同一个函数暴露给 LLM：Action[fetch](https://...)。
"""

from __future__ import annotations

import re
from html import unescape

import httpx

# 单次 GET 超时。文章页偶发很慢，宁可空结果也不要卡死整个 ReAct 循环。
TIMEOUT_SECONDS = 8

# 不带浏览器头时，不少站点直接返回验证码页或空页。
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 去掉 HTML 标签：<p>国乒</p> → 国乒
_TAG = re.compile(r"<[^>]+>")

# 验证码 / 反爬页特征。命中后不要把「请完成验证」当成新闻正文。
_BLOCKED_MARKERS = (
    "百度安全验证",
    "此验证码用于确认",
    "antispider",
    "anti.min.css",
    "wappass",
)


def is_blocked_page(html: str) -> bool:
    """
    判断这次 GET 是不是验证码 / 反爬页。

    旧搜索解析器踩过这个坑：把搜狗验证码页页脚
    （返回首页、企业推广）当成了搜索结果。
    """
    return any(marker in html for marker in _BLOCKED_MARKERS)


def get_html(url: str, params: dict[str, str] | None = None) -> str:
    """
    GET 一个 URL，返回原始 HTML 字符串。

    follow_redirects=True：搜索引擎常用跳转链接，跟着跳才能落到文章页。
    失败时抛 httpx 异常，由调用方决定是换引擎还是写成 Observation 错误。

    Args:
        url: 完整 http/https 地址。
        params: 查询参数，例如 360 搜索的 {"q": "国乒"}。

    Returns:
        响应正文（HTML）。
    """
    with httpx.Client(
        timeout=TIMEOUT_SECONDS,
        headers=HEADERS,
        follow_redirects=True,
    ) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.text


def html_to_text(html: str, limit: int = 2000) -> str:
    """
    把 HTML 收成一段可读纯文本。

    步骤：
    1. 删掉 script / style / noscript（里面不是给人看的）
    2. 其余标签换成空格
    3. HTML 实体解码（&amp; → &）
    4. 连续空白压成一个空格
    5. 超长截断，避免 Observation 把 LLM 上下文撑爆

    Args:
        html: 原始 HTML。
        limit: 最多保留多少字符。

    Returns:
        纯文本；超长末尾加省略号。
    """
    html = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", html)
    html = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", html)
    text = unescape(_TAG.sub(" ", html))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def fetch_text(url: str, limit: int = 2000) -> str:
    """
    GET 一个 URL，返回可读正文。

    验证码页返回空字符串（不是抛异常）：
    搜索补摘要时可以跳过这一条，fetch 工具再把它写成「被拦截」。

    Args:
        url: 文章页地址。
        limit: 正文截断长度。

    Returns:
        纯文本；被拦截或无正文时返回 ""。
    """
    html = get_html(url)
    if is_blocked_page(html):
        return ""
    return html_to_text(html, limit=limit)
