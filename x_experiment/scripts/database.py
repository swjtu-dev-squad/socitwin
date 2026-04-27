"""OASIS Twitter话题数据库查询接口"""

import sqlite3
from typing import List, Dict, Optional, Any
import logging
from pathlib import Path


class DatabaseClient:
    """OASIS Twitter话题数据库客户端"""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        self.connection = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self) -> None:
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row
            self.logger.debug(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise

    def close(self) -> None:
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.logger.debug("Database connection closed")

    def _ensure_connection(self) -> None:
        """确保数据库连接已建立"""
        if not self.connection:
            self.connect()

    def get_topic_info(self, topic_key: str, platform: str = "twitter") -> Dict[str, Any]:
        """获取话题信息"""
        self._ensure_connection()

        query = """
        SELECT topic_label, post_count, reply_count, user_count
        FROM topics
        WHERE platform = ? AND topic_key = ?
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (platform, topic_key))
            row = cursor.fetchone()
            if row:
                return {
                    'topic_label': row['topic_label'],
                    'post_count': row['post_count'],
                    'reply_count': row['reply_count'],
                    'user_count': row['user_count']
                }
            self.logger.warning(f"Topic not found: platform={platform}, topic_key={topic_key}")
            return {}
        except sqlite3.Error as e:
            self.logger.error(f"Failed to query topic info: {e}")
            raise

    def get_posts_for_topic(self, topic_key: str, platform: str = "twitter", limit: int = 50) -> List[Dict[str, Any]]:
        """获取指定话题的相关帖子"""
        self._ensure_connection()

        query = """
        SELECT c.text, c.like_count, c.reply_count
        FROM contents c
        JOIN content_topics ct ON c.external_content_id = ct.external_content_id
        WHERE ct.platform = ? AND ct.topic_key = ? AND c.platform = ?
        ORDER BY c.like_count DESC, c.reply_count DESC
        LIMIT ?
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (platform, topic_key, platform, limit))
            rows = cursor.fetchall()
            posts = [{'text': r['text'], 'like_count': r['like_count'], 'reply_count': r['reply_count']} for r in rows]
            self.logger.debug(f"Found {len(posts)} posts for topic: {topic_key}")
            return posts
        except sqlite3.Error as e:
            self.logger.error(f"Failed to query posts for topic: {e}")
            raise

    def get_majority_opinion_samples(self, topic_key: str, platform: str = "twitter", sample_size: int = 20) -> List[str]:
        """获取多数意见样本（按点赞数排序的帖子文本）"""
        posts = self.get_posts_for_topic(topic_key, platform, sample_size)
        samples = [post['text'] for post in posts if post['text'] and post['text'].strip()]
        self.logger.debug(f"Extracted {len(samples)} opinion samples for topic: {topic_key}")
        return samples

    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            self._ensure_connection()
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            return cursor.fetchone()[0] == 1
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False

    def get_topic_count(self, platform: str = "twitter") -> int:
        """获取指定平台的话题数量"""
        self._ensure_connection()
        query = "SELECT COUNT(*) as count FROM topics WHERE platform = ? AND type = 'twitter'"
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, (platform,))
            row = cursor.fetchone()
            return row['count'] if row else 0
        except sqlite3.Error as e:
            self.logger.error(f"Failed to count topics: {e}")
            return 0


if __name__ == "__main__":
    import sys
    db_path = "/home/liz/socitwin/backend/data/datasets/oasis_datasets.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    client = DatabaseClient(db_path)
    client.test_connection()
