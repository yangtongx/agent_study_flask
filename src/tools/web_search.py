"""
网络搜索工具 — 国内可访问的搜索页。

=== 为什么不用百度 / 搜狗抓首页？===
无 Cookie 的 httpx 请求会被拦：百度返回「安全验证」，搜狗返回验证码页。
旧解析器把验证码页页脚（返回首页、企业推广）当成了搜索结果。

现在默认 360 搜索（so.com），没有有效结果再用必应中国（cn.bing.com）。
搜到链接后会 fetch 前几篇正文，避免只有标题。
单独的 fetch 工具也可以按 URL 再读一篇。
"""

from __future__ import annotations

import asyncio
import re
from html import unescape
from urllib.parse import urlparse

from src.tools.base_tool import BaseTool
from src.tools.http_fetch import fetch_text, get_html, is_blocked_page

# Observation 最多列几条。太多会占满后续 LLM 上下文。
_MAX_RESULTS = 5
# 整次搜索（含补正文）的总超时。比单次 GET 宽，因为可能连打两个引擎再 fetch。
_TOTAL_TIMEOUT = 25
# 每条结果正文摘要长度。完整正文交给 fetch 工具。
_SNIPPET_LIMIT = 400
# 只给前几条补正文，避免一次搜索打爆对方站点。
_FETCH_PAGES = 3

# 去掉 HTML 标签：<em>国乒</em> → 国乒
_TAG = re.compile(r"<[^>]+>")

# 360 结果标题：<h3 class="res-title"><a href="..." data-mdurl="真实地址">标题</a>
_360_ITEM = re.compile(
    r"<h3[^>]*class=\"[^\"]*res-title[^\"]*\"[^>]*>\s*<a\b([^>]*)>(.*?)</a>",
    re.I | re.S,
)
# 必应中国结果标题：<h2><a href="真实地址">标题</a>
_BING_ITEM = re.compile(
    r"<h2[^>]*>\s*<a\b([^>]*)>(.*?)</a>",
    re.I | re.S,
)

# 验证码页 / 页脚常见锚文本。长度太短的标题也当噪声丢掉。
_JUNK_TITLES = {
    "返回首页",
    "返回首页>>",
    "返回首页>",
    "企业推广",
    "关于搜狗",
    "免责声明",
    "意见反馈",
    "问题反馈",
    "登录",
    "注册",
    "更多",
}
# 搜狗页脚、备案站等，不是新闻来源。
_JUNK_HOSTS = {
    "fuwu.sogou.com",
    "corp.sogou.com",
    "fankui.sogou.com",
    "www.miibeian.gov.cn",
}


def _strip_tags(text: str) -> str:
    """标题里常带 <em> 高亮，先剥掉再给 LLM 看。"""
    return unescape(_TAG.sub("", text)).replace("\n", " ").strip()


def _attr(attrs: str, name: str) -> str:
    """从 <a ...> 的属性串里取出指定属性值。"""
    match = re.search(rf'{re.escape(name)}="([^"]+)"', attrs, re.I)
    return unescape(match.group(1)).strip() if match else ""


def _is_blocked_page(html: str) -> bool:
    """验证码页：不要往下解析，直接当这次搜索失败。"""
    return is_blocked_page(html)


def _is_useful_result(title: str, href: str) -> bool:
    """
    过滤页脚、验证码、搜索引擎自身链接。

    只要标题或域名像导航栏，Observation 就会再次变成「返回首页>>」。
    """
    if not title or title in _JUNK_TITLES or len(title) < 6:
        return False
    if not href.startswith("http://") and not href.startswith("https://"):
        return False
    host = urlparse(href).netloc.lower()
    if host in _JUNK_HOSTS:
        return False
    # 结果链回搜索页本身，没有文章可读
    if "so.com/s?" in href or "bing.com/search" in href:
        return False
    return True


def parse_360_html(html: str) -> list[dict]:
    """
    从 360 搜索结果页抽出标题和真实链接。

    360 的 href 经常是 so.com/link?m=... 跳转地址。
    真实文章 URL 在 data-mdurl 里，优先用它，后面 fetch 才打得开。

    Returns:
        [{"title", "href", "body"}, ...]，body 先空着，由 _fill_snippets 补。
    """
    if _is_blocked_page(html):
        return []
    rows: list[dict] = []
    seen: set[str] = set()
    for attrs, inner in _360_ITEM.findall(html):
        title = _strip_tags(inner)
        href = _attr(attrs, "data-mdurl") or _attr(attrs, "href")
        if not _is_useful_result(title, href) or href in seen:
            continue
        seen.add(href)
        rows.append({"title": title, "href": href, "body": ""})
        if len(rows) >= _MAX_RESULTS:
            break
    return rows


def parse_bing_html(html: str) -> list[dict]:
    """
    从必应中国结果页抽出标题和链接。

    360 被拦或解析为空时的后备。验证码页同样直接返回空列表。
    """
    if _is_blocked_page(html):
        return []
    rows: list[dict] = []
    seen: set[str] = set()
    for attrs, inner in _BING_ITEM.findall(html):
        title = _strip_tags(inner)
        href = _attr(attrs, "href")
        if not _is_useful_result(title, href) or href in seen:
            continue
        seen.add(href)
        rows.append({"title": title, "href": href, "body": ""})
        if len(rows) >= _MAX_RESULTS:
            break
    return rows


class WebSearchTool(BaseTool):
    """
    国内网页搜索。参数是自然语言查询字符串。

    === 调用链 ===
    run() → 线程里 _search()（先 360 再必应）→ _fill_snippets() 补正文
    → 格式化成 Observation 文本还给 LLM。
    """

    @property
    def name(self) -> str:
        """工具名称。对应 Action[web_search](...)。"""
        return "web_search"

    @property
    def description(self) -> str:
        """这段会出现在 system prompt 里，LLM 靠它决定何时上网查。"""
        return (
            "搜索公开网页，获取新闻、资料和实时信息。"
            "参数：搜索词，例如 '国乒 最新消息'。"
            "训练数据里没有、需要查资料或查近况时使用。"
        )

    async def run(self, args: str) -> str:
        """
        搜索并把结果格式化成 Observation。

        httpx 是同步的，放到线程里跑，避免卡住 async 的 AgentLoop。
        失败不抛异常：错误字符串原样回到 LLM，让它换关键词或改用 fetch。

        Args:
            args: 搜索词，例如 "国乒 最新消息"。

        Returns:
            带编号的标题 / URL / 摘要，或中文错误信息。
        """
        query = args.strip()
        if not query:
            return "搜索失败：查询词为空"

        try:
            rows = await asyncio.wait_for(
                asyncio.to_thread(self._search, query),
                timeout=_TOTAL_TIMEOUT,
            )
        except TimeoutError:
            return "搜索失败：网络超时。请稍后重试，或把关键词写得更具体一点。"
        except Exception as e:
            return f"搜索失败：{self._short_error(e)}"

        if not rows:
            return f"没有找到结果：{query}"

        self._fill_snippets(rows)

        lines = [f"搜索结果：{query}"]
        for i, row in enumerate(rows, start=1):
            title = str(row.get("title") or "").strip()
            url = str(row.get("href") or row.get("url") or "").strip()
            snippet = str(row.get("body") or row.get("snippet") or "").strip()
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   {url}")
            if snippet:
                lines.append(f"   {snippet}")
        return "\n".join(lines)

    def _search(self, query: str) -> list[dict]:
        """
        先 360，没有有效结果再用必应中国。

        测试时 monkeypatch 这一层，不必真的上网。
        两个引擎都抛错时，把最后一个异常抛出去，由 run() 收成中文错误。
        """
        last_error: BaseException | None = None
        for fetcher in (self._search_360, self._search_bing):
            try:
                rows = fetcher(query)
                if rows:
                    return rows
            except Exception as e:
                last_error = e
                continue
        if last_error:
            raise last_error
        return []

    def _fill_snippets(self, rows: list[dict]) -> None:
        """
        对前几条结果 fetch 正文，避免 Observation 只有标题没有内容。

        跳过 so.com/link 跳转地址：那不是文章页，GET 回去还是搜索中间页。
        某一篇失败就留空，不影响其它条。
        """
        filled = 0
        for row in rows:
            if filled >= _FETCH_PAGES:
                break
            if str(row.get("body") or "").strip():
                continue
            href = str(row.get("href") or "")
            if not href.startswith("http") or "so.com/link" in href:
                continue
            try:
                row["body"] = fetch_text(href, limit=_SNIPPET_LIMIT)
            except Exception:
                row["body"] = ""
            filled += 1

    def _search_360(self, query: str) -> list[dict]:
        """默认引擎：360 搜索。"""
        html = get_html("https://www.so.com/s", {"q": query})
        return parse_360_html(html)

    def _search_bing(self, query: str) -> list[dict]:
        """360 没有有效结果时的后备。"""
        html = get_html("https://cn.bing.com/search", {"q": query})
        return parse_bing_html(html)

    @staticmethod
    def _short_error(exc: BaseException) -> str:
        """
        把异常收成短中文，不要把整段 URL 堆进 Observation。

        httpx 超时信息里常带着完整搜索 URL，LLM 看到会误当成搜索结果。
        """
        blob = f"{type(exc).__name__} {exc}".lower()
        if "timeout" in blob or "timed out" in blob:
            return "网络超时，请稍后重试。"
        text = str(exc).strip() or type(exc).__name__
        if len(text) > 160:
            return text[:160] + "…"
        return text
