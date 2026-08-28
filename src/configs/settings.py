"""
配置中心 — 使用 pydantic-settings 加载并校验环境变量。

=== 什么是 pydantic？===
Pydantic 是 Python 最流行的数据校验库。
你定义一个类，声明字段类型，Pydantic 自动：
1. 从 .env 文件或环境变量读取值
2. 校验类型（比如 agent_max_iterations 必须是 int）
3. 类型转换（从字符串 "10" 转成整数 10）

=== 什么是 lru_cache？===
@lru_cache 是一个装饰器，让函数只执行一次，之后返回缓存结果。
这样整个程序只有一个 Settings 实例（单例模式），不会重复读取 .env 文件。
"""

from __future__ import annotations

# lru_cache 装饰器：让函数结果缓存起来，下次调用直接返回缓存
from functools import lru_cache

# Field 用于给字段添加元信息（默认值、描述等）
from pydantic import Field

# BaseSettings 是 pydantic-settings 的基类，
# 继承它后，类字段会自动从环境变量/.env 文件读取
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置。

    从 .env 文件自动加载，支持环境变量覆盖。

    === 优先级 ===
    环境变量 > .env 文件 > 代码默认值

    例如 agent_max_iterations：
    - 如果设了环境变量 AGENT_MAX_ITERATIONS=5 → 值是 5
    - 否则如果 .env 里有 AGENT_MAX_ITERATIONS=10 → 值是 10
    - 否则用代码里的默认值 10

    === 字段名映射规则 ===
    pydantic 不区分大小写，统一转大写匹配：
    agent_max_iterations → 环境变量 AGENT_MAX_ITERATIONS
    openai_api_key → 环境变量 OPENAI_API_KEY
    """

    # model_config 配置如何读取 .env 文件
    model_config = SettingsConfigDict(
        env_file=".env",             # 从项目根目录的 .env 文件读取
        env_file_encoding="utf-8",   # 文件编码（支持中文）
        extra="ignore",              # .env 里有多余的字段就忽略，不报错
    )

    # =================================================================
    # LLM 相关配置（DeepSeek）
    # =================================================================
    # DeepSeek API 兼容 OpenAI 格式，所以字段名用通用的 llm_ 前缀
    # 在 .env 中配置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 即可
    llm_api_key: str = Field(default="sk-xxx", description="LLM API Key (DeepSeek)")
    llm_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="LLM API base URL (DeepSeek)",
    )
    llm_model: str = Field(
        default="deepseek-v4-flash",
        description="LLM model name (DeepSeek)",
    )

    # =================================================================
    # Agent 相关配置
    # =================================================================
    agent_max_iterations: int = Field(default=10, description="Max ReAct loop iterations")
    agent_memory_window: int = Field(default=20, description="Short-term memory window size")
    agent_debug: bool = Field(default=True, description="Enable debug logging")
    # handmade = 手写 ReAct（自己解析 Thought/Action 文本，默认，方便测试注入假 LLM）
    # agentscope = AgentScope 2.0 官方 Agent（原生 function calling）
    # 对应环境变量 AGENT_BACKEND，非法值会在 factory.get_backend() 里回落到 handmade
    agent_backend: str = Field(
        default="handmade",
        description="Main agent backend: handmade (own ReAct) or agentscope (AgentScope 2.0)",
    )

    # =================================================================
    # RAG（检索增强生成）
    # =================================================================
    # 检索时返回几段；太多会占满 prompt，太少可能漏答案
    rag_top_k: int = Field(default=3, description="How many chunks to retrieve")
    rag_persist_path: str = Field(
        default="./data/rag",
        description="Directory for the JSON vector index",
    )
    rag_knowledge_dir: str = Field(
        default="./data/knowledge",
        description="Seed markdown/txt files ingested when the index is empty",
    )

    # =================================================================
    # Database 相关配置（PostgreSQL）
    # =================================================================
    pg_uri: str = Field(
        default="postgresql://user:pass@localhost:5432/agent_study",
        description="PostgreSQL connection URI",
    )

    # =================================================================
    # Vector Store 相关配置
    # =================================================================
    chroma_persist_path: str = Field(
        default="./data/chroma",
        description="ChromaDB persistence path",
    )


@lru_cache
def get_settings() -> Settings:
    """
    获取全局配置单例。

    使用 lru_cache 确保整个进程只加载一次。
    第一次调用时读取 .env 文件创建 Settings 实例，
    之后所有调用都返回同一个实例。

    Returns:
            全局唯一的 Settings 实例。
    """
    return Settings()
