import os
import sqlite3
from .config import DB_PATH

def get_db_connection():
    """获取数据库连接"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"数据库不存在：{DB_PATH}")
    return sqlite3.connect(DB_PATH)

def load_topics(conn):
    """读取所有话题（原逻辑不变）"""
    cursor = conn.execute(
        "SELECT platform, topic_key, topic_label, post_count, reply_count, user_count FROM topics"
    )
    topics = []
    for row in cursor.fetchall():
        topics.append({
            "platform": row[0],
            "topic_key": row[1],
            "topic_label": row[2],
            "post_count": row[3] or 0,
            "reply_count": row[4] or 0,
            "user_count": row[5] or 0,
        })
    return topics