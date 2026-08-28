"""
PostgreSQL 连接管理。

=== 连接池 vs 每次新建连接？===
每次新建 TCP 连接 + 认证握手要 50-100ms，很浪费。
psycopg2 的连接池复用已有连接，避免重复握手。

但我们用 ThreadedConnectionPool（线程安全的连接池），
因为 Flask 默认是同步请求，可能在多线程里处理。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from src.configs.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 全局连接池实例（懒加载）
_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    """
    获取/创建全局连接池。

    连接池配置：
    - minconn=2: 保持 2 个空闲连接
    - maxconn=10: 最多 10 个并发连接

    创建一次，全局复用。
    """
    global _pool
    if _pool is None:
        settings = get_settings()
        logger.info("Creating PostgreSQL connection pool...")
        _pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=settings.pg_uri,
        )
        logger.info("PostgreSQL connection pool created (min=2, max=10)")
    return _pool


@contextmanager
def get_conn() -> Generator:
    """
    获取数据库连接（上下文管理器）。

    用法：
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                rows = cur.fetchall()

    with 语句确保用完后自动归还连接到池中，不会泄漏连接。
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()  # 自动提交事务
    except Exception:
        conn.rollback()  # 出错自动回滚
        raise
    finally:
        pool.putconn(conn)  # 归还连接到池


def init_db() -> None:
    """
    初始化数据库表结构。

    在服务启动时调用一次，创建所需的表（IF NOT EXISTS 保证幂等）。
    """
    logger.info("Initializing database tables...")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 对话历史表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id          BIGSERIAL PRIMARY KEY,
                    session_id  VARCHAR(64) NOT NULL,
                    role        VARCHAR(20) NOT NULL,
                    content     TEXT NOT NULL,
                    iterations  INTEGER DEFAULT 0,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            # 按 session_id 查询需要索引
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_history_session
                ON chat_history (session_id, created_at);
            """)

    logger.info("Database tables initialized.")
