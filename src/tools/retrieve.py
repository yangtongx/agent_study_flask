"""
检索工具 — Agent 的「翻笔记」的手。

=== RAG 在 ReAct 里怎么走？===
用户：年假有几天？
知识专家：Thought: 这在知识库里。
          Action[retrieve](年假天数)
工具：    命中《请假制度》里「年假 10 天」那一段
专家：    Final Answer: 根据知识库，年假是 10 天。

LLM 自己并不「查询数据库」；它只是决定调用 retrieve。
真正算向量、比相似度的是本文件后面的 Python。
"""

from __future__ import annotations

from src.configs.settings import get_settings
from src.rag.store import VectorStore, get_vector_store
from src.tools.base_tool import BaseTool


class RetrieveTool(BaseTool):
    """
    从向量知识库检索相关段落。

    测试时可传入自己的 store，避免碰到全局单例和磁盘文件。
    """

    def __init__(
        self,
        store: VectorStore | None = None,
        top_k: int | None = None,
    ) -> None:
        self._store = store
        self._top_k = top_k

    @property
    def name(self) -> str:
        return "retrieve"

    @property
    def description(self) -> str:
        return (
            "从知识库检索相关资料。"
            "输入：要查的问题或关键词，例如 '年假有几天'。"
            "返回最相关的若干段落；没有则说明知识库为空或未命中。"
        )

    async def run(self, args: str) -> str:
        query = (args or "").strip()
        if not query:
            return "检索失败：查询不能为空。"
        settings = get_settings()
        top_k = self._top_k or settings.rag_top_k
        db = self._store if self._store is not None else get_vector_store()
        hits = db.query(query, top_k=top_k)
        if not hits:
            return "知识库中没有找到相关内容。不要编造，请如实告诉用户。"

        lines = [f"检索到 {len(hits)} 条相关资料："]
        for i, hit in enumerate(hits, start=1):
            lines.append(
                f"[{i}] 来源={hit.source} 相似度={hit.score:.3f}\n{hit.text}"
            )
        return "\n\n".join(lines)
