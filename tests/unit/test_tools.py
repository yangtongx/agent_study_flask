"""工具模块单元测试。"""

import pytest

from src.tools.calculator import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_basic():
    """测试基本算术：2 + 3 应该等于 5。"""
    calc = CalculatorTool()
    result = await calc.run("2 + 3")
    # 结果字符串中应该包含 "5"
    assert "5" in result


@pytest.mark.asyncio
async def test_calculator_complex():
    """测试复合表达式：2 + 3 * 4 应该等于 14（先乘后加）。"""
    calc = CalculatorTool()
    result = await calc.run("2 + 3 * 4")
    assert "14" in result


@pytest.mark.asyncio
async def test_calculator_power():
    """测试幂运算：2 ** 10 应该等于 1024。"""
    calc = CalculatorTool()
    result = await calc.run("2 ** 10")
    assert "1024" in result


@pytest.mark.asyncio
async def test_calculator_invalid():
    """测试非法输入：import os 不应该执行，应返回错误。"""
    calc = CalculatorTool()
    result = await calc.run("import os")
    assert "失败" in result


def test_calculator_name_and_description():
    """测试工具的元信息（name 和 description 属性）。"""
    calc = CalculatorTool()
    assert calc.name == "calculator"
    assert "计算" in calc.description


@pytest.mark.asyncio
async def test_web_search_formats_results(monkeypatch):
    """搜索工具应把标题、链接、摘要格式化成 Observation 文本。"""
    from src.tools.web_search import WebSearchTool

    def fake_search(self, query: str) -> list[dict]:
        assert query == "Python 3.13"
        return [
            {
                "title": "Python 3.13.0",
                "href": "https://www.python.org/downloads/",
                "body": "Released on October 7, 2024.",
            }
        ]

    monkeypatch.setattr(WebSearchTool, "_search", fake_search)
    tool = WebSearchTool()
    result = await tool.run("Python 3.13")
    assert "搜索结果" in result
    assert "Python 3.13.0" in result
    assert "https://www.python.org/downloads/" in result
    assert "October 7, 2024" in result


@pytest.mark.asyncio
async def test_web_search_empty_query():
    """空查询不应去请求搜索引擎。"""
    from src.tools.web_search import WebSearchTool

    result = await WebSearchTool().run("   ")
    assert "搜索失败" in result
    assert "空" in result


@pytest.mark.asyncio
async def test_web_search_no_results(monkeypatch):
    """搜不到时 Observation 用中文说明，而不是空字符串。"""
    from src.tools.web_search import WebSearchTool

    monkeypatch.setattr(WebSearchTool, "_search", lambda self, query: [])
    result = await WebSearchTool().run("zzzz-not-a-real-topic")
    assert "没有找到结果" in result


def test_web_search_name_and_description():
    """工具名必须是 web_search，描述里要提到搜索。"""
    from src.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert "搜索" in tool.description


def test_default_tools_includes_calculator_and_search():
    """默认装备：计算器、搜索、fetch，顺序固定方便对照。"""
    from src.tools import default_tools

    names = [t.name for t in default_tools()]
    assert names == ["calculator", "web_search", "fetch"]


@pytest.mark.asyncio
async def test_web_search_timeout_is_short_chinese(monkeypatch):
    """超时不应把整段 URL 堆进 Observation。"""
    from src.tools.web_search import WebSearchTool

    def boom(self, query: str) -> list[dict]:
        raise TimeoutError(
            "error sending request for url "
            "(https://search.yahoo.com/search?p=景甜) > operation timed out"
        )

    monkeypatch.setattr(WebSearchTool, "_search", boom)
    result = await WebSearchTool().run("景甜 孙宇晨")
    assert "搜索失败" in result
    assert "超时" in result
    assert "yahoo.com" not in result.lower()


def test_parse_360_html_prefers_real_url():
    """360 的 href 是跳转链，真实文章地址在 data-mdurl。"""
    from src.tools.web_search import parse_360_html

    html = """
    <h3 class="res-title"><a href="https://www.so.com/link?m=abc"
        data-mdurl="https://sports.sohu.com/a/1050119086"
        target="_blank"><em>国乒最新</em>消息!孙颖莎、王曼昱</a></h3>
    """
    rows = parse_360_html(html)
    assert rows[0]["title"] == "国乒最新消息!孙颖莎、王曼昱"
    assert rows[0]["href"] == "https://sports.sohu.com/a/1050119086"


def test_parse_sogou_captcha_footer_is_ignored():
    """验证码页页脚（返回首页、企业推广）不能当成搜索结果。"""
    from src.tools.web_search import parse_360_html, parse_bing_html

    html = """
    <title>搜狗搜索</title>
    <link rel="stylesheet" href="static/css/anti.min.css?v=1"/>
    <a href="/">返回首页>></a>
    <a href="http://fuwu.sogou.com/">企业推广</a>
    <a href="http://corp.sogou.com/">关于搜狗</a>
    """
    assert parse_360_html(html) == []
    assert parse_bing_html(html) == []


def test_web_search_falls_back_to_bing(monkeypatch):
    """360 没结果时应改走必应中国。"""
    from src.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    monkeypatch.setattr(tool, "_search_360", lambda query: [])
    monkeypatch.setattr(
        tool,
        "_search_bing",
        lambda query: [{"title": "中国乒乓球协会官方网站", "href": "https://www.ctta.cn/", "body": ""}],
    )
    rows = tool._search("国乒 最新")
    assert rows[0]["href"] == "https://www.ctta.cn/"


def test_html_to_text_strips_tags():
    """script 丢掉，可见正文留下。"""
    from src.tools.http_fetch import html_to_text

    text = html_to_text("<html><script>bad()</script><p>国乒夺冠</p></html>")
    assert "国乒夺冠" in text
    assert "bad" not in text


@pytest.mark.asyncio
async def test_fetch_requires_http_url():
    """不是 http/https 的参数应直接失败，不要当 URL 去 GET。"""
    from src.tools.web_fetch import FetchTool

    result = await FetchTool().run("不是网址")
    assert "抓取失败" in result


@pytest.mark.asyncio
async def test_fetch_returns_page_text(monkeypatch):
    """成功时应带上「网页正文」标记和页面文本。"""
    from src.tools import web_fetch as fetch_mod
    from src.tools.web_fetch import FetchTool

    monkeypatch.setattr(fetch_mod, "fetch_text", lambda url, limit=3000: "孙颖莎晋级决赛")
    result = await FetchTool().run("https://sports.sohu.com/a/1")
    assert "孙颖莎晋级决赛" in result
    assert "网页正文" in result
