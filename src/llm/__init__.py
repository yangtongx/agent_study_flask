"""
LLM 模块 — 客户端封装与工厂。

=== 什么是 LLM 客户端？===
LLM（Large Language Model，大语言模型）比如 GPT-4，
它运行在云端服务器上。我们要调用它的 API，
需要一个"客户端"来发送请求和接收响应。

=== 为什么不直接调 API？===
1. 直接调用需要写一堆 HTTP 请求代码，重复且容易出错
2. 封装后，切换模型（从 OpenAI 换到 Claude）只改一个地方
3. 可以统一加缓存、错误处理、日志

=== 工厂模式 ===
LLMFactory 是"工厂"，你告诉它要哪个模型，
它帮你创建对应的客户端。这样调用方不用关心具体实现。
"""

from src.llm.base_client import BaseLLMClient
from src.llm.factory import LLMFactory

__all__ = ["BaseLLMClient", "LLMFactory"]
