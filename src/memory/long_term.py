"""
长期记忆 — 向量数据库存储与检索（预留接口）。

=== 什么是长期记忆？===
短期记忆只记住最近几轮对话，长期记忆可以记住几天前甚至几个月前的信息。

=== 什么是向量数据库？===
把文字转换成"向量"（一串数字），然后用相似度来搜索。
比如你存了 "Python 是编程语言"，之后搜索 "什么是 Python" 就能找到它。
即使搜索词和存储的原文不完全一样，语义相近就能匹配。

=== 什么是 stub？===
stub 是"桩"的意思 — 一个占位实现。
现在这些方法只打印日志不做真正的事，以后接入 ChromaDB 后再实现。
这样不影响 Agent 的基本运行，方便先跑通流程。
"""

from __future__ import annotations

# Any 表示任意类型，用在还没有确定具体类型的地方
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LongTermMemory:
    """
    长期记忆 — 基于向量相似度检索的历史知识。

    当前为 stub 实现，后续接入 ChromaDB。

    === 以后实现后的效果 ===
    - store(): 把知识转成向量存入数据库
    - retrieve(): 把查询转成向量，找到最相似的知识
    - forget(): 删除不再需要的记忆
    """

    def __init__(self, persist_path: str | None = None) -> None:
        """
        初始化长期记忆。

        Args:
            persist_path: 数据库持久化路径（数据存在硬盘上的位置）。
        """
        self.persist_path = persist_path
        # _client 以后会持有 ChromaDB 客户端实例
        self._client: Any = None
        logger.info("LongTermMemory initialized (stub mode)")

    def store(self, content: str, metadata: dict | None = None) -> str:
        """
        存储一条记忆。

        以后实现时：
        1. 把 content 转成向量（用 embedding 模型）
        2. 存入 ChromaDB
        3. 返回记忆 ID

        Args:
            content: 要存储的文本内容。
            metadata: 附加信息（如来源、时间等），方便以后筛选。

        Returns:
            记忆 ID（用于以后删除或引用）。
        """
        logger.debug("Store (stub): %s", content[:100])
        return "stub-id"

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        检索相关记忆。

        以后实现时：
        1. 把 query 转成向量
        2. 在数据库中找最相似的 top_k 条记忆
        3. 返回匹配结果

        Args:
            query: 查询文本。
            top_k: 返回最相似的 k 条结果。

        Returns:
            匹配的记忆列表，每条包含内容和相似度分数。
        """
        logger.debug("Retrieve (stub): %s", query[:100])
        return []

    def forget(self, memory_id: str) -> bool:
        """
        遗忘指定记忆。

        就像人类会遗忘不重要的信息一样，
        Agent 也需要删除过时的记忆，避免记忆库膨胀。

        Args:
            memory_id: 要删除的记忆 ID。

        Returns:
            是否删除成功。
        """
        logger.debug("Forget (stub): %s", memory_id)
        return True
