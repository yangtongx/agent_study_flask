"""
Tools 模块 — Agent 的工具层。

=== 什么是工具？===
LLM 本身只会生成文字，不能执行操作。
工具就是让 Agent "长手"的方式：
- 计算器工具：做数学计算
- 搜索工具：搜索网络
- API 客户端：调用外部服务

LLM 决定用哪个工具、传什么参数，工具执行后把结果返回给 LLM。
"""

from src.tools.base_tool import BaseTool
from src.tools.calculator import CalculatorTool
from src.tools.delegate import DelegateTool
from src.tools.retrieve import RetrieveTool

__all__ = ["BaseTool", "CalculatorTool", "DelegateTool", "RetrieveTool"]
