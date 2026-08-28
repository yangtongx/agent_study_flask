"""
Safety 模块 — 输入/输出安全过滤。

=== 为什么需要安全过滤？===
AI Agent 连接了强大的 LLM 和各种工具，如果不做防护，
恶意用户可能利用它来：
1. Prompt Injection（提示注入）：骗 AI 泄露系统提示或执行危险操作
2. 信息泄露：AI 可能在回复中暴露用户的敏感信息

两层防护：
- InputFilter：检查用户输入是否包含恶意指令
- OutputFilter：对 AI 输出做敏感信息脱敏
"""

from src.safety.input_filter import InputFilter
from src.safety.output_filter import OutputFilter

__all__ = ["InputFilter", "OutputFilter"]
