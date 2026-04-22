"""
数据库工具类

统一表结构，适用于 Twitter/Instagram 等平台。
"""

import sqlite3
from pathlib import Path

CREATE_SCHEMA = """
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    platform TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'dataset',
    external_user_id TEXT NOT NULL,
    username TEXT,
    display_name TEXT,
    bio TEXT,
    location TEXT,
    verified INTEGER DEFAULT 0,
    follower_count INTEGER,
    following_count INTEGER,
    tweet_count INTEGER,
    post_count INTEGER,
    user_type TEXT,
    profile_json TEXT,
    raw_json TEXT,
    PRIMARY KEY (platform, external_user_id)
);
CREATE INDEX IF NOT EXISTS idx_users_platform ON users(platform);

-- 内容表
CREATE TABLE IF NOT EXISTS contents (
    platform TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'dataset',
    external_content_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    author_external_user_id TEXT,
    parent_external_content_id TEXT,
    root_external_content_id TEXT,
    text TEXT,
    language TEXT,
    created_at TEXT,
    like_count INTEGER,
    reply_count INTEGER,
    share_count INTEGER,
    view_count INTEGER,
    raw_json TEXT,
    PRIMARY KEY (platform, external_content_id)
);
CREATE INDEX IF NOT EXISTS idx_contents_platform ON contents(platform);
CREATE INDEX IF NOT EXISTS idx_contents_platform_author ON contents(platform, author_external_user_id);

-- 话题表
CREATE TABLE IF NOT EXISTS topics (
    platform TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'dataset',
    topic_key TEXT NOT NULL,
    topic_label TEXT NOT NULL,
    topic_type TEXT NOT NULL,
    trend_rank INTEGER,
    post_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    user_count INTEGER DEFAULT 0,
    first_seen_at TEXT,
    last_seen_at TEXT,
    news_external_id TEXT,
    raw_json TEXT,
    PRIMARY KEY (platform, topic_key)
);
CREATE INDEX IF NOT EXISTS idx_topics_platform ON topics(platform);

-- 内容-话题关联表
CREATE TABLE IF NOT EXISTS content_topics (
    platform TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'dataset',
    external_content_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,
    relevance_score REAL DEFAULT 1.0,
    PRIMARY KEY (platform, external_content_id, topic_key)
);
CREATE INDEX IF NOT EXISTS idx_content_topics_platform_topic ON content_topics(platform, topic_key);

-- 用户-话题关联表
CREATE TABLE IF NOT EXISTS user_topics (
    platform TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'dataset',
    topic_key TEXT NOT NULL,
    external_user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content_count INTEGER DEFAULT 0,
    news_external_id TEXT,
    PRIMARY KEY (platform, topic_key, external_user_id)
);
CREATE INDEX IF NOT EXISTS idx_user_topics_platform_topic ON user_topics(platform, topic_key);

"""


SCHEMA_MIGRATIONS: dict[str, dict[str, str]] = {
    "users": {
        "type": '"type" TEXT DEFAULT \'dataset\'',
        "tweet_count": "tweet_count INTEGER",
        "post_count": "post_count INTEGER",
        "profile_json": "profile_json TEXT",
    },
    "contents": {
        "type": '"type" TEXT DEFAULT \'dataset\'',
    },
    "topics": {
        "type": '"type" TEXT DEFAULT \'dataset\'',
        "trend_rank": "trend_rank INTEGER",
        "reply_count": "reply_count INTEGER DEFAULT 0",
        "news_external_id": "news_external_id TEXT",
    },
    "content_topics": {
        "type": '"type" TEXT DEFAULT \'dataset\'',
    },
    "user_topics": {
        "type": '"type" TEXT DEFAULT \'dataset\'',
        "news_external_id": "news_external_id TEXT",
    },
}


class DatasetDB:
    """数据集数据库操作"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self):
        """连接数据库"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        return self

    def close(self):
        """关闭数据库"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def ensure_schema(self):
        """创建统一表结构"""
        self.conn.executescript(CREATE_SCHEMA)
        self._migrate_schema()
        self.conn.commit()

    def _table_columns(self, table: str) -> set[str]:
        return {row[1] for row in self.conn.execute(f'PRAGMA table_info("{table}")')}

    def _migrate_schema(self) -> None:
        """为旧库补齐新列。SQLite 的 CREATE TABLE IF NOT EXISTS 不会更新旧表。"""
        for table, columns in SCHEMA_MIGRATIONS.items():
            existing = self._table_columns(table)
            if not existing:
                continue
            for column_name, column_sql in columns.items():
                if column_name not in existing:
                    self.conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {column_sql}')
            if "type" in columns:
                self.conn.execute(
                    f'UPDATE "{table}" SET "type" = platform WHERE "type" IS NULL OR "type" = ""',
                )

    def upsert(self, table: str, row: dict, keys: tuple) -> None:
        """插入或更新记录"""
        cols = [k for k in row.keys() if k in self._table_columns(table)]
        if not cols:
            return
        names = ', '.join(f'"{k}"' for k in cols)
        placeholders = ', '.join('?' for _ in cols)
        conflict = ', '.join(f'"{k}"' for k in keys)
        updates = ', '.join(f'"{k}"=excluded."{k}"' for k in cols if k not in keys)

        sql = f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})'
        if updates:
            sql += f' ON CONFLICT ({conflict}) DO UPDATE SET {updates}'
        else:
            sql += f' ON CONFLICT ({conflict}) DO NOTHING'

        self.conn.execute(sql, [row[k] for k in cols])

    # ========== 用户 ==========
    def insert_user(self, user: dict) -> None:
        """插入用户"""
        self.upsert("users", user, ("platform", "external_user_id"))

    # ========== 内容 ==========
    def insert_content(self, content: dict) -> None:
        """插入内容"""
        self.upsert("contents", content, ("platform", "external_content_id"))

    # ========== 话题 ==========
    def insert_topic(self, topic: dict) -> None:
        """插入话题"""
        self.upsert("topics", topic, ("platform", "topic_key"))

    def add_content_topic(
        self,
        platform: str,
        content_id: str,
        topic_key: str,
        score: float = 1.0,
        row_type: str | None = None,
    ) -> None:
        """关联内容与话题"""
        self.upsert(
            "content_topics",
            {
                "platform": platform,
                "type": row_type or platform,
                "external_content_id": content_id,
                "topic_key": topic_key,
                "relevance_score": score,
            },
            ("platform", "external_content_id", "topic_key"),
        )

    def add_user_topic(
        self,
        platform: str,
        topic_key: str,
        user_id: str,
        role: str,
        count: int = 0,
        row_type: str | None = None,
        news_external_id: str | None = None,
    ) -> None:
        """关联用户与话题"""
        self.upsert(
            "user_topics",
            {
                "platform": platform,
                "type": row_type or platform,
                "topic_key": topic_key,
                "external_user_id": user_id,
                "role": role,
                "content_count": count,
                "news_external_id": news_external_id,
            },
            ("platform", "topic_key", "external_user_id"),
        )

    # ========== 事务 ==========
    def begin_transaction(self):
        """开始事务"""
        self.conn.execute("BEGIN")

    def commit(self):
        """提交事务"""
        self.conn.commit()

    def rollback(self):
        """回滚事务"""
        self.conn.rollback()
