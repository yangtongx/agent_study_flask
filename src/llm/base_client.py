"""
LLM 客户端基类 — 统一接口定义。

=== 什么是抽象基类？===
和 BaseTool 一样，BaseLLMClient 定义了"接口"（chat 方法），
所有具体的 LLM 客户端都必须实现它。

这样 AgentLoop 只依赖 BaseLLMClient，不依赖具体的 OpenAIClient。
以后换模型时，只需要新写一个 ClaudeClient，不用改 AgentLoop 的代码。

=== 依赖倒置原则 ===
高层模块（AgentLoop）不应该依赖低层模块（OpenAIClient），
两者都应该依赖抽象（BaseLLMClient）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """
    所有 LLM 客户端的基类。

    子类需实现 chat() 方法，封装具体的 API 调用。

    === chat 方法的输入输出 ===
    输入：messages（消息列表），格式：
        [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"},
        ]

    输出：LLM 生成的文本，比如 "你好！有什么可以帮你的？"
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        发送对话请求。

        Args:
            messages: OpenAI 格式的消息列表。
                OpenAI API 的标准格式，每条消息有 role 和 content：
                - role="system": 系统提示（定义 AI 人设）
                - role="user": 用户消息
                - role="assistant": AI 的回复

            temperature: 采样温度（0~2）。
                - 0: 最确定（每次回答几乎一样）
                - 0.7: 适中（有创意但不跑题）
                - 1.5+: 非常随机（可能胡说）
                默认 0.7 是创意和稳定的平衡点。

            max_tokens: 最大输出 token 数。
                token 是 LLM 处理文本的最小单位，
                1 个中文字约 1-2 个 token。
                None 表示不限制。

        Returns:
            LLM 生成的文本。
        """
        ...
