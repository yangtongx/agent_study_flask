"""
LLM 工厂 — 统一创建客户端，解耦具体实现。

=== 什么是工厂模式？===
想象你去买咖啡：
- 你只说"来杯拿铁"（接口）
- 咖啡机（工厂）负责制作具体的那杯拿铁（实现）
- 你不需要知道咖啡机内部怎么运作

LLMFactory 就是这个"咖啡机"：
- 调用 LLMFactory.create("openai") → 返回 OpenAIClient 实例
- 以后加 Claude：LLMFactory.create("claude") → 返回 ClaudeClient 实例
- 调用方只需要知道 provider 名称，不用关心内部实现

=== 为什么用 @staticmethod？===
create 方法不依赖实例属性，只是"纯函数"。
用 @staticmethod 表示它不访问 self，语义更清晰。
"""

from __future__ import annotations

from src.llm.base_client import BaseLLMClient
from src.llm.openai_client import OpenAIClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMFactory:
    """
    模型工厂 — 根据配置创建 LLM 客户端。

    扩展新模型时只需:
        1. 新建 xxx_client.py 实现 BaseLLMClient
        2. 在此添加分支
    """

    @staticmethod
    def create(provider: str = "openai") -> BaseLLMClient:
        """
        创建 LLM 客户端实例。

        Args:
            provider: 模型提供方名称。
                      "openai" → OpenAIClient
                      以后可以加 "claude"、"local" 等。

        Returns:
            LLM 客户端实例（BaseLLMClient 的子类）。

        Raises:
            ValueError: 不支持的 provider。
        """
        # providers 字典：名称 → 类
        # 以后加新模型，只需要在这里加一行
        # 例如: {"openai": OpenAIClient, "claude": ClaudeClient}
        providers = {
            "openai": OpenAIClient,
        }

        # 检查 provider 是否在字典里
        if provider not in providers:
            raise ValueError(f"Unknown LLM provider: {provider}. Available: {list(providers)}")

        logger.info("Creating LLM client: %s", provider)

        # providers[provider]() 等同于 OpenAIClient()
        # 从字典取出类，然后实例化
        return providers[provider]()
