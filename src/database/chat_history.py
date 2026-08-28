"""
对话历史持久化 — 把对话记录存到 PostgreSQL。

=== 表结构 ===
chat_history:
    id          主键，自增
    session_id  会话 ID（同一次对话的标识）
    role        消息角色（user / assistant）
    content     消息内容
    iterations  ReAct 循环次数（仅 assistant 消息有）
    created_at  创建时间

=== 为什么用 session_id？===
一个用户可能有多轮对话，每次对话是一个 "session"。
用 session_id 区分不同对话，加载历史时只取当前 session 的。
"""

from __future__ import annotations

from psycopg2.extras import RealDictCursor

from src.database.connection import get_conn
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ChatHistoryRepo:
    """对话历史数据库操作。"""

    @staticmethod
    def save_message(
        session_id: str,
        role: str,
        content: str,
        iterations: int = 0,
    ) -> int:
        """
        保存一条对话消息。

        Args:
            session_id: 会话 ID。
            role: 消息角色（"user" 或 "assistant"）。
            content: 消息内容。
            iterations: ReAct 循环次数（仅 assistant 记录）。

        Returns:
            新记录的 ID。
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_history (session_id, role, content, iterations)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id;
                """, (session_id, role, content, iterations))
                record_id = cur.fetchone()[0]
        logger.debug("Saved message: session=%s, role=%s, id=%d", session_id, role, record_id)
        return record_id

    @staticmethod
    def get_history(session_id: str, limit: int = 20) -> list[dict]:
        """
        获取指定会话的对话历史。

        Args:
            session_id: 会话 ID。
            limit: 最多返回几条消息（从最新往前数）。

        Returns:
            消息列表（按时间正序），格式同 OpenAI messages：
            [{"role": "user", "content": "..."}, ...]
        """
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT role, content
                    FROM chat_history
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                """, (session_id, limit))
                rows = cur.fetchall()

        # 反转使时间正序（最早的消息在前）
        rows.reverse()

        # 转为 OpenAI messages 格式
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    @staticmethod
    def clear_session(session_id: str) -> int:
        """
        清除指定会话的所有历史。

        Args:
            session_id: 会话 ID。

        Returns:
            删除的记录数。
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chat_history WHERE session_id = %s;",
                    (session_id,)
                )
                deleted = cur.rowcount
        logger.info("Cleared %d messages for session=%s", deleted, session_id)
        return deleted
