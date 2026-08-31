"""
Tools 模块 — Agent 的工具层。

=== 什么是工具？===
LLM 本身只会生成文字，不能执行操作。
工具就是让 Agent "长手"的方式：
- 计算器工具：做数学计算
- 搜索工具：按关键词找网页
- fetch 工具：按 URL 打开网页读正文
- API 客户端：调用外部服务

LLM 决定用哪个工具、传什么参数，工具执行后把结果返回给 LLM。

=== 加新工具改哪里？===
实现一个 BaseTool 子类，然后加进 default_tools()。
CLI（react_agent.py）和 HTTP（routes.py）都从这里取列表，不用改两处。
"""

from src.tools.base_tool import BaseTool
from src.tools.calculator import CalculatorTool
from src.tools.web_fetch import FetchTool
from src.tools.web_search import WebSearchTool


def default_tools() -> list[BaseTool]:
    """
    CLI 和 HTTP 共用的默认工具列表。

    顺序无所谓，AgentLoop 按 name 查找。
    当前装备：计算器、网页搜索、按 URL fetch 正文。
    """
    return [CalculatorTool(), WebSearchTool(), FetchTool()]


__all__ = ["BaseTool", "CalculatorTool", "WebSearchTool", "FetchTool", "default_tools"]
