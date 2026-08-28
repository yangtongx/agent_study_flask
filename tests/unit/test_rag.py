"""
RAG 单元测试 — 向量化、切块、检索、RetrieveTool。不调用真实 LLM。
"""

from __future__ import annotations

import pytest

from src.rag.chunker import chunk_text
from src.rag.embeddings import cosine, embed
from src.rag.ingest import ingest_text
from src.rag.store import VectorStore
from src.tools.retrieve import RetrieveTool


def test_similar_texts_have_higher_cosine():
    """「年假有几天」应更接近年假制度，而不是算术说明。"""
    leave = embed("正式员工每年享有 10 个工作日年假")
    query = embed("年假有几天")
    other = embed("用计算器做乘法 15 乘 23")
    assert cosine(query, leave) > cosine(query, other)


def test_chunk_text_splits_paragraphs():
    text = "第一段内容。\n\n第二段也有一些字。"
    chunks = chunk_text(text, chunk_size=400)
    assert len(chunks) == 2
    assert "第一段" in chunks[0]
    assert "第二段" in chunks[1]


def test_vector_store_query_returns_best_hit():
    store = VectorStore(persist_path=None)
    store.add(["年假每年 10 个工作日。", "HTTP 服务默认端口是 8000。"], source="demo")
    hits = store.query("年假几天", top_k=1)
    assert hits
    assert "10" in hits[0].text
    assert hits[0].source == "demo"


def test_ingest_replace_same_source():
    store = VectorStore(persist_path=None)
    assert ingest_text("旧内容：年假 5 天", source="leave.md", store=store) >= 1
    ingest_text("新内容：年假 10 天", source="leave.md", store=store, replace=True)
    hits = store.query("年假", top_k=3)
    joined = " ".join(h.text for h in hits)
    assert "10" in joined
    assert "5 天" not in joined


@pytest.mark.asyncio
async def test_retrieve_tool_formats_hits():
    store = VectorStore(persist_path=None)
    store.add(["病假每月不超过 3 天按全额工资发放。"], source="leave-policy.md")
    tool = RetrieveTool(store=store, top_k=1)
    result = await tool.run("病假工资怎么发")
    assert "3" in result
    assert "leave-policy" in result


@pytest.mark.asyncio
async def test_retrieve_tool_empty_query():
    tool = RetrieveTool(store=VectorStore(persist_path=None))
    result = await tool.run("  ")
    assert "不能为空" in result
