"""
网页抓取工具 — 按 URL fetch 正文。

=== 什么时候用 fetch，什么时候用 web_search？===
- web_search：只有关键词，不知道具体网址 → 先搜出标题和链接
- fetch：用户已经给了链接，或搜索结果里有一篇值得打开 → GET 这一页

搜索只能给出标题和链接。要读某篇新闻，再对这个链接做一次 GET。
参数必须是 http/https 地址，例如 Action[fetch](https://www.ctta.cn/)
"""

from __future__ import annotations

import asyncio

from src.tools.base_tool import BaseTool
from src.tools.http_fetch import fetch_text

# 整次工具调用的上限（含排队）。比单次 GET 略宽，避免刚下完就被掐断。
_TOTAL_TIMEOUT = 15
# 正文截断。太长会占满后续 LLM 上下文。
_TEXT_LIMIT = 3000


class FetchTool(BaseTool):
    """
    按 URL 拉取网页正文。

    === 和搜索工具的分工 ===
    WebSearchTool 负责「找链接」，FetchTool 负责「打开这一篇」。
    真正发 HTTP 的是 http_fetch.fetch_text，两边共用，避免两套解析。
    """

    @property
    def name(self) -> str:
        """工具名称。必须是英文，对应 Action[fetch](...)。"""
        return "fetch"

    @property
    def description(self) -> str:
        """这段会出现在 system prompt 里，LLM 靠它决定何时打开网页。"""
        return (
            "打开一个网页并读取正文。"
            "参数：完整 URL，必须以 http:// 或 https:// 开头。"
            "搜索到链接后，若需要具体内容，再用本工具抓取该链接。"
        )

    async def run(self, args: str) -> str:
        """
        GET 指定网址，返回纯文本 Observation。

        httpx 是同步客户端。AgentLoop 是 async，所以放到线程里跑，
        避免卡住整个事件循环。失败不抛异常，写成中文错误还给 LLM。

        Args:
            args: 完整 URL。允许包一层尖括号（模型有时会写成 <https://...>）。

        Returns:
            「网页正文：URL + 文本」，或「抓取失败：…」。
        """
        url = args.strip().strip("<>")
        if not url.startswith("http://") and not url.startswith("https://"):
            return "抓取失败：参数必须是 http 或 https 开头的网址"

        try:
            text = await asyncio.wait_for(
                asyncio.to_thread(fetch_text, url, _TEXT_LIMIT),
                timeout=_TOTAL_TIMEOUT,
            )
        except TimeoutError:
            return "抓取失败：网络超时"
        except Exception as e:
            return f"抓取失败：{e}"

        if not text:
            return f"抓取失败：页面无正文或被验证码拦截\n{url}"
        return f"网页正文：{url}\n{text}"
