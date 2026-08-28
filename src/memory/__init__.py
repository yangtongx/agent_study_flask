"""
Memory 模块 — 短期/长期记忆系统。

=== 为什么 Agent 需要记忆？===
如果你问 Agent "我叫什么名字"，它得记住你之前告诉过它。
没有记忆，每次对话都像第一次见面。

=== 两种记忆 ===
1. 短期记忆：记住最近几轮对话（就像你脑子里的临时便签）
2. 长期记忆：记住很久以前的知识（向量库 RAG，见 src/rag/）
"""

from src.memory.manager import MemoryManager

__all__ = ["MemoryManager"]
