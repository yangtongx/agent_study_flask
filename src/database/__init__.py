"""
Database 模块 — PostgreSQL 连接与持久化。

=== 为什么需要数据库？===
之前的记忆系统只存在内存里（ShortTermMemory 用 deque），
服务重启后对话历史全丢了。PostgreSQL 把对话记录持久化到磁盘，
重启后历史还在。

=== 用 psycopg2 而非 asyncpg？===
psycopg2 是最成熟的 PostgreSQL 驱动，同步 API 简单可靠。
Agent 的 DB 操作不频繁（每次对话写一条记录），同步足够。
如果后期有高并发需求，可以换 asyncpg。
"""

from src.database.connection import get_conn, init_db
from src.database.chat_history import ChatHistoryRepo

__all__ = ["get_conn", "init_db", "ChatHistoryRepo"]
