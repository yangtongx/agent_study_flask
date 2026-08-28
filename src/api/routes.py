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

# 工厂：按 AGENT_BACKEND 给出手写 Coordinator 或 AgentScope 主 Agent
from src.agents.factory import MainAgent, create_main_agent, display_agent_name, get_backend
from src.api.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeSearchResponse,
)
from src.database import init_db
from src.rag.ingest import ingest_text
from src.rag.store import get_vector_store
from src.utils.exceptions import MaxIterationsError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Blueprint：一组路由。server.py 里 register_blueprint(bp) 后才会生效
bp = Blueprint("api", __name__)

# =====================================================================
# 全局状态
# =====================================================================
# 按 session_id 缓存主 Agent：同一会话复用（记忆连续），不同会话隔离
_agents: dict[str, MainAgent] = {}
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


def get_or_create_agent(session_id: str) -> MainAgent:
    """
    按 session_id 获取或创建主 Agent。

    同一 session_id 复用同一个主 Agent → 记忆连续。
    不同 session_id 创建新实例 → 记忆隔离。
    具体实现由 AGENT_BACKEND 决定（handmade / agentscope）。
    """
    if session_id not in _agents:
        logger.info("Creating main agent for session=%s", session_id[:8])
        _agents[session_id] = create_main_agent(session_id=session_id)
    return _agents[session_id]


@bp.get("/")
def index():
    """首页。"""
    return jsonify({
        "name": "My Agent API",
        "version": "0.1.0",
        "mode": "multi-agent",
        "backend": get_backend(),  # handmade 或 agentscope，方便确认当前实现
        "endpoints": {
            "health": "GET /health",
            "chat": "POST /chat",
            "docs": "GET /docs",
            "knowledge": "POST /knowledge",
            "knowledge_search": "GET /knowledge/search",
        },
    })


@bp.get("/health")
def health():
    """健康检查。"""
    db_ok = _ensure_db()
    store = get_vector_store()
    body = HealthResponse(
        status="ok",
        agent=display_agent_name(),  # CoordinatorAgent 或 ScopeCoordinator
        database="connected" if db_ok else "unavailable",
        sub_agents=["math_agent", "writer_agent", "knowledge_agent", "general_agent"],
        backend=get_backend(),
        knowledge_chunks=store.count(),
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
        "mode": "multi-agent",
        "backend": get_backend(),  # 当前是 handmade 还是 agentscope
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
                "method": "POST",
                "path": "/knowledge",
                "description": "灌入知识。JSON body: {content: str, source?: str}",
            },
            {
                "method": "GET",
                "path": "/knowledge/search",
                "description": "检索知识库。Query: q=关键词&top_k=3",
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


@bp.post("/knowledge")
def knowledge_ingest():
    """
    灌入知识。正文会被切块、向量化，写入全局知识库。
    之后 knowledge_agent 用 retrieve 就能搜到。
    """
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"detail": "Request body must be a JSON object"}), 422
    try:
        req = KnowledgeIngestRequest.model_validate(payload)
    except ValidationError as e:
        return jsonify({"detail": e.errors()}), 422

    n = ingest_text(req.content, source=req.source or "api")
    body = KnowledgeIngestResponse(
        chunks=n,
        source=req.source or "api",
        total=get_vector_store().count(),
    )
    return jsonify(body.model_dump())


@bp.get("/knowledge/search")
def knowledge_search():
    """调试用：不经过 Agent，直接看检索命中了哪几段。"""
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"detail": "query parameter q is required"}), 422
    try:
        top_k = int(request.args.get("top_k") or 3)
    except ValueError:
        return jsonify({"detail": "top_k must be an integer"}), 422

    hits = get_vector_store().query(query, top_k=max(top_k, 1))
    body = KnowledgeSearchResponse(
        query=query,
        hits=[
            {
                "id": h.id,
                "source": h.source,
                "score": round(h.score, 4),
                "text": h.text,
            }
            for h in hits
        ],
    )
    return jsonify(body.model_dump())
