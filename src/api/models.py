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

    answer: str = Field(description="给用户看的回复：本轮 Thought（如有）+ 最终答案")
    agent: str = Field(description="处理此请求的 Agent 名称")
    iterations: int = Field(description="ReAct 循环执行的迭代次数")
    session_id: str = Field(description="本次对话的会话 ID（下次传入可延续上下文）")


class HealthResponse(BaseModel):
    """健康检查响应模型。"""

    status: str = Field(description="服务状态")
    agent: str = Field(description="Agent 名称")
    database: str = Field(description="数据库连接状态")
