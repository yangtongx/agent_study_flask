"""
路由定义 — Agent HTTP API 的所有接口。

=== 这个文件做什么？===
用 Flask Blueprint 声明 URL：
    GET  /        服务简介
    GET  /health  健康检查
    GET  /docs    接口说明
    POST /chat    真正聊天

Blueprint 可以理解成「一组路由的打包」，最后在 server.py 里挂到 Flask app 上。

=== 为什么路由是同步的，Agent 却是 async？===
Agent 调 LLM 用的是 async/await。
经典 Flask 视图是同步函数。这里用 asyncio.run() 包一层：
在一次请求里跑完整个异步 ReAct 循环，对初学者最直观。
"""

from __future__ import annotations

import asyncio
import uuid

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from src.agents.react_agent import ReactAgent
from src.api.models import ChatRequest, ChatResponse, HealthResponse
from src.core.agent_loop import AgentLoop
from src.database import init_db
from src.tools import default_tools
from src.utils.exceptions import MaxIterationsError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Blueprint：一组路由。server.py 里 register_blueprint(bp) 后才会生效
bp = Blueprint("api", __name__)

# =====================================================================
# 全局状态
# =====================================================================
# 按 session_id 缓存 Agent 实例：同一会话复用 Agent（保持记忆连续性）
# 不同 session 各自独立，互不干扰
_agents: dict[str, ReactAgent] = {}
_db_initialized = False


def _ensure_db() -> bool:
    """确保数据库已初始化。返回 DB 是否可用。"""
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
        except Exception as e:
            logger.warning("DB init failed, running without DB: %s", e)
            return False
    return True


def get_or_create_agent(session_id: str) -> ReactAgent:
    """
    按 session_id 获取或创建 Agent。

    同一 session_id 复用同一个 Agent 实例 → 记忆连续。
    不同 session_id 创建新 Agent → 记忆隔离。
    """
    if session_id not in _agents:
        logger.info("Creating new Agent for session=%s", session_id[:8])
        agent = ReactAgent.__new__(ReactAgent)

        from src.agents.base_agent import BaseAgent
        from src.llm.factory import LLMFactory
        from src.memory.manager import MemoryManager

        BaseAgent.__init__(agent, name="ReactAgent")
        agent.llm_client = LLMFactory.create()
        agent.tools = default_tools()
        agent.memory = MemoryManager(session_id=session_id)
        agent.max_iterations = 10
        agent.loop = AgentLoop(
            llm_client=agent.llm_client,
            tools=agent.tools,
            memory=agent.memory,
            max_iterations=agent.max_iterations,
        )
        _agents[session_id] = agent
    return _agents[session_id]


@bp.get("/")
def index():
    """首页。"""
    return jsonify({
        "name": "My Agent API",
        "version": "0.1.0",
        "endpoints": {
            "health": "GET /health",
            "chat": "POST /chat",
            "docs": "GET /docs",
        },
    })


@bp.get("/health")
def health():
    """健康检查。"""
    db_ok = _ensure_db()
    body = HealthResponse(
        status="ok",
        agent="ReactAgent",
        database="connected" if db_ok else "unavailable",
    )
    return jsonify(body.model_dump())


@bp.get("/docs")
def docs():
    """
    接口说明。

    Flask 没有自动生成的交互式文档页，
    这里返回一份 JSON，方便浏览器直接打开查看。
    """
    return jsonify({
        "title": "My Agent API",
        "version": "0.1.0",
        "framework": "Flask",
        "endpoints": [
            {
                "method": "GET",
                "path": "/",
                "description": "服务简介",
            },
            {
                "method": "GET",
                "path": "/health",
                "description": "健康检查，含 database 是否连通",
            },
            {
                "method": "POST",
                "path": "/chat",
                "description": "聊天。JSON body: {message: str, session_id?: str}",
            },
            {
                "method": "GET",
                "path": "/docs",
                "description": "本页",
            },
        ],
    })


@bp.post("/chat")
def chat():
    """
    聊天接口。

    传入 session_id 可以延续多轮对话（Agent 会记住之前的上下文）。
    不传 session_id 会自动生成一个新的。
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"detail": "Request body must be a JSON object"}), 422

    try:
        req = ChatRequest.model_validate(payload)
    except ValidationError as e:
        return jsonify({"detail": e.errors()}), 422

    _ensure_db()

    session_id = req.session_id or str(uuid.uuid4())
    logger.info("Chat request: session=%s, message=%s", session_id[:8], req.message[:200])

    try:
        agent = get_or_create_agent(session_id)
        # Agent.run() 是 async，Flask 视图是同步，用 asyncio.run 跑完这一次请求
        answer = asyncio.run(agent.run(req.message))
        iterations = agent.loop._iteration_count
        body = ChatResponse(
            answer=answer,
            agent=agent.name,
            iterations=iterations,
            session_id=session_id,
        )
        return jsonify(body.model_dump())

    except MaxIterationsError as e:
        logger.error("Agent max iterations: %s", e)
        return jsonify({"detail": f"Agent exceeded max iterations: {e}"}), 508

    except Exception as e:
        logger.error("Chat failed: %s", e, exc_info=True)
        return jsonify({"detail": f"Internal error: {e}"}), 500
