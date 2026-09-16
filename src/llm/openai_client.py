"""
OpenAI 客户端 — 封装 OpenAI Chat Completions API。

=== 什么是 OpenAI API？===
OpenAI 提供 HTTP 接口，你把消息发到它的服务器，
它返回 GPT 模型生成的回复。

请求格式（POST）：
    POST https://api.openai.com/v1/chat/completions
    Headers: Authorization: Bearer sk-xxx
    Body: {"model": "gpt-4o", "messages": [...]}

响应格式（JSON）：
    {"choices": [{"message": {"content": "LLM 的回复"}}]}

=== 为什么用 httpx 不用 openai SDK？===
减少依赖。httpx 是异步 HTTP 客户端，轻量且足够。
openai SDK 封装了更多功能，但也引入了更多依赖。
对于学习 Agent 原理，直接用 HTTP 更直观。
"""

from __future__ import annotations

# 导入配置（API Key 等敏感信息从 .env 读取）
from src.configs.settings import get_settings

# 导入基类
from src.llm.base_client import BaseLLMClient

# 导入自定义异常
from src.utils.exceptions import LLMError

# LangSmith：把这一次 LLM 调用画成 Trace 里的 llm.chat 节点
from src.utils.langsmith_setup import llm_traceable

# 导入日志
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient(BaseLLMClient):
    """
    OpenAI API 客户端。

    使用 httpx 进行异步 HTTP 请求，不依赖 openai SDK。
    """

    def __init__(self) -> None:
        """
        初始化客户端。

        从配置文件读取 API Key、Base URL 和模型名称。
        这些值存在 .env 文件里（不会提交到 Git，保护密钥安全）。
        """
        settings = get_settings()
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        logger.info("LLM client initialized: model=%s, base_url=%s", self.model, self.base_url)

    @llm_traceable
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """
        调用 OpenAI Chat Completions API。

        完整流程：
        1. 组装请求头（带上 API Key 认证）
        2. 组装请求体（模型名、消息、温度等）
        3. 发送 HTTP POST 请求
        4. 检查响应状态码
        5. 从 JSON 响应中提取回复文本

        Args:
            messages: 消息列表。
            temperature: 采样温度。
            max_tokens: 最大 token。

        Returns:
            LLM 回复文本。

        Raises:
            LLMError: API 调用失败（网络错误、认证失败等）。
        """
        # 延迟导入 httpx：只在真正需要时才 import
        # 这样如果没装 httpx，但也没用到这个客户端，不会报错
        try:
            import httpx
        except ImportError as e:
            raise LLMError("httpx not installed") from e

        # 构建 API URL
        url = f"{self.base_url}/chat/completions"

        # HTTP 请求头
        # Authorization: Bearer 是 API 认证的标准方式
        # 类似出示你的"门禁卡"（API Key）让服务器识别你
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 请求体（JSON 格式）
        payload = {
            "model": self.model,           # 用哪个模型
            "messages": messages,          # 对话消息
            "temperature": temperature,   # 采样温度
        }
        # 如果指定了 max_tokens，加入请求体
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            # httpx.AsyncClient 创建异步 HTTP 客户端
            # timeout=60.0 表示最多等 60 秒
            # async with 确保用完后自动关闭连接（释放资源）
            async with httpx.AsyncClient(timeout=60.0) as client:
                # 发送 POST 请求
                resp = await client.post(url, json=payload, headers=headers)

                # raise_for_status() 在 HTTP 状态码非 2xx 时抛异常
                # 例如 401（认证失败）、429（限流）、500（服务器错误）
                resp.raise_for_status()

                # 解析 JSON 响应
                data = resp.json()

                # 从 JSON 中提取回复文本
                # 响应结构: {"choices": [{"message": {"content": "回复内容"}}]}
                # [0] 取第一个 choice
                return data["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            # HTTP 错误（如 401 认证失败）
            logger.error("OpenAI API error: %s %s", e.response.status_code, e.response.text[:200])
            raise LLMError(f"OpenAI API error: {e.response.status_code}") from e
        except Exception as e:
            # 其他错误（如网络超时、DNS 解析失败）
            logger.error("OpenAI request failed: %s", e)
            raise LLMError(f"Request failed: {e}") from e
