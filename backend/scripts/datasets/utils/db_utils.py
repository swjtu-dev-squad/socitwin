"""
统一数据集 SQLite 工具。
"""

import sqlite3
from pathlib import Path


CREATE_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS content_topics (
    platform TEXT NOT NULL,
    "type" TEXT NOT NULL DEFAULT 'dataset',
    external_content_id TEXT NOT NULL,
    topic_key TEXT NOT NULL,
    relevance_score REAL DEFAULT 1.0,
    PRIMARY KEY (platform, external_content_id, topic_key)
);
CREATE INDEX IF NOT EXISTS idx_content_topics_platform_topic ON content_topics(platform, topic_key);

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
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection | None = None

    def __enter__(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.conn:
            self.conn.close()

    def ensure_schema(self) -> None:
        self.conn.executescript(CREATE_SCHEMA)
        self._migrate_schema()
        self.conn.commit()

    def _table_columns(self, table: str) -> set[str]:
        return {row[1] for row in self.conn.execute(f'PRAGMA table_info("{table}")')}

    def _migrate_schema(self) -> None:
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
