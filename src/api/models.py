"""
请求/响应模型 — 定义 API 接口的数据格式。

新增 session_id 字段：调用方可以传入会话 ID，
Agent 会加载该会话的历史对话，实现多轮对话。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求模型。"""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户输入的消息文本",
    )
    session_id: str | None = Field(
        default=None,
        description="会话 ID。传入相同值可延续多轮对话。不传则创建新会话。",
    )


class ChatResponse(BaseModel):
    """聊天响应模型。"""

    answer: str = Field(description="Agent 的最终回复")
    agent: str = Field(description="处理此请求的 Agent 名称")
    iterations: int = Field(description="ReAct 循环执行的迭代次数")
    session_id: str = Field(description="本次对话的会话 ID（下次传入可延续上下文）")


class HealthResponse(BaseModel):
    """健康检查响应模型。"""

    status: str = Field(description="服务状态")
    agent: str = Field(description="Agent 名称")
    database: str = Field(description="数据库连接状态")
    sub_agents: list[str] = Field(
        default_factory=list,
        description="主 Agent 可调度的子 Agent 名称",
    )
    # 告诉调用方当前走的是手写 ReAct 还是 AgentScope，方便排查「怎么突然换了一套」
    backend: str = Field(
        default="handmade",
        description="主 Agent 实现：handmade 或 agentscope",
    )
    knowledge_chunks: int = Field(
        default=0,
        description="向量知识库当前片段数量",
    )


class KnowledgeIngestRequest(BaseModel):
    """灌入知识的请求。"""

    content: str = Field(..., min_length=1, max_length=100000, description="要写入知识库的正文")
    source: str | None = Field(default="api", description="来源标记，例如文件名")


class KnowledgeIngestResponse(BaseModel):
    """灌入结果。"""

    chunks: int = Field(description="本次新写入的片段数")
    source: str = Field(description="来源标记")
    total: int = Field(description="知识库当前总片段数")


class KnowledgeSearchResponse(BaseModel):
    """直接检索（不经过 Agent）的结果，方便调试 RAG。"""

    query: str
    hits: list[dict]
