import math

def compute_divergence(conn, platform, topic_key):
    """计算扩散指数（原代码 100% 保留）"""
    cursor = conn.execute(
        "SELECT external_content_id FROM content_topics WHERE topic_key = ? AND platform = ?",
        (topic_key, platform)
    )
    content_ids = [row[0] for row in cursor.fetchall()]
    content_count = len(content_ids)

    if content_count == 0:
        return {
            "content_count": 0,
            "multi_topic_count": 0,
            "multi_topic_ratio": 0.0,
            "unique_other_topics": 0,
            "avg_topics_per_content": 0.0,
            "divergence_index": 0.0,
        }

    cursor = conn.execute(
        """
        SELECT ct2.topic_key, COUNT(DISTINCT ct1.external_content_id)
        FROM content_topics ct1
        JOIN content_topics ct2
          ON ct1.platform = ct2.platform
          AND ct1.external_content_id = ct2.external_content_id
        WHERE ct1.topic_key = ? AND ct1.platform = ?
          AND ct2.topic_key != ct1.topic_key
        GROUP BY ct2.topic_key
        """,
        (topic_key, platform)
    )
    other_topic_rows = cursor.fetchall()
    unique_other_topics = len(other_topic_rows)

    cursor = conn.execute(
        """
        SELECT DISTINCT ct1.external_content_id
        FROM content_topics ct1
        JOIN content_topics ct2
          ON ct1.platform = ct2.platform
          AND ct1.external_content_id = ct2.external_content_id
        WHERE ct1.topic_key = ? AND ct1.platform = ?
          AND ct2.topic_key != ct1.topic_key
        """,
        (topic_key, platform)
    )
    multi_topic_content_ids = set(row[0] for row in cursor.fetchall())
    multi_topic_count = len(multi_topic_content_ids)
    multi_topic_ratio = multi_topic_count / content_count

    cursor = conn.execute(
        """
        SELECT ct1.external_content_id, COUNT(ct2.topic_key) as topic_cnt
        FROM content_topics ct1
        JOIN content_topics ct2
          ON ct1.platform = ct2.platform
          AND ct1.external_content_id = ct2.external_content_id
        WHERE ct1.topic_key = ? AND ct1.platform = ?
        GROUP BY ct1.external_content_id
        """,
        (topic_key, platform)
    )
    topic_counts = [row[1] for row in cursor.fetchall()]
    avg_topics_per_content = sum(topic_counts) / len(topic_counts) if topic_counts else 1.0

    divergence_index = multi_topic_ratio * math.log2(1 + unique_other_topics)

    return {
        "content_count": content_count,
        "multi_topic_count": multi_topic_count,
        "multi_topic_ratio": multi_topic_ratio,
        "unique_other_topics": unique_other_topics,
        "avg_topics_per_content": avg_topics_per_content,
        "divergence_index": divergence_index,
    }

def cluster_topics(topic_results):
    """话题聚类（原代码不变）"""
    for topic in topic_results:
        di = topic["divergence_index"]
        if di > 0.1:
            topic["cluster"] = "高扩散（容易分化）"
            topic["color"] = "#e74c3c"
        elif 0 < di <= 0.1:
            topic["cluster"] = "中等扩散"
            topic["color"] = "#f39c12"
        else:
            topic["cluster"] = "低扩散（不易分化）"
            topic["color"] = "#27ae60"
    return topic_results