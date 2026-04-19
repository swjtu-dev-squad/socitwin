"""
数据导出工具

提供从 OASIS 数据库导出模拟数据的功能，
支持多种格式和筛选选项。
"""

import csv
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.simulation import ExportConfig

logger = logging.getLogger(__name__)


class OASISDataExporter:
    """
    OASIS 数据导出器

    从 OASIS SQLite 数据库导出模拟数据，
    支持多种格式和过滤选项。
    """

    def __init__(self, db_path: str):
        """
        初始化导出器

        Args:
            db_path: OASIS 数据库文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        """上下文管理器入口"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 以字典形式返回结果
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        if self.conn:
            self.conn.close()

    # ========================================================================
    # 数据查询方法
    # ========================================================================

    def get_all_data(self, config: ExportConfig) -> Dict[str, Any]:
        """
        获取所有请求数据

        Args:
            config: 导出配置

        Returns:
            导出数据字典
        """
        data = {}

        if config.include_agents:
            data["users"] = self._get_users_data()

        if config.include_posts:
            data["posts"] = self._get_posts_data()

        if config.include_interactions:
            data["interactions"] = self._get_interactions_data()

        if config.include_comments:
            data["comments"] = self._get_comments_data()

        if config.include_follows:
            data["follows"] = self._get_follows_data()

        # 添加元数据
        data["metadata"] = self._get_metadata()

        return data

    def _get_users_data(self) -> List[Dict[str, Any]]:
        """获取用户数据"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                user_id,
                agent_id,
                user_name,
                name,
                bio,
                created_at,
                num_followings,
                num_followers
            FROM user
            ORDER BY user_id
        """)

        return [dict(row) for row in cursor.fetchall()]

    def _get_posts_data(self) -> List[Dict[str, Any]]:
        """获取帖子数据"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                post_id,
                user_id,
                original_post_id,
                content,
                quote_content,
                created_at,
                num_likes,
                num_dislikes,
                num_shares,
                num_reports
            FROM post
            ORDER BY created_at DESC
        """)

        return [dict(row) for row in cursor.fetchall()]

    def _get_interactions_data(self) -> List[Dict[str, Any]]:
        """获取交互数据"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                user_id,
                created_at,
                action,
                info
            FROM trace
            ORDER BY created_at DESC
        """)

        interactions = []
        for row in cursor.fetchall():
            interaction = dict(row)
            # 解析 JSON info
            try:
                if interaction["info"]:
                    interaction["info"] = json.loads(interaction["info"])
            except json.JSONDecodeError:
                pass
            interactions.append(interaction)

        return interactions

    def _get_comments_data(self) -> List[Dict[str, Any]]:
        """获取评论数据"""
        assert self.conn is not None
        try:
            cursor = self.conn.execute("""
                SELECT
                    comment_id,
                user_id,
                post_id,
                content,
                created_at,
                num_likes,
                num_dislikes
                FROM comment
                ORDER BY created_at DESC
            """)

            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # comment 表可能不存在
            return []

    def _get_follows_data(self) -> List[Dict[str, Any]]:
        """获取关注关系数据"""
        assert self.conn is not None
        try:
            cursor = self.conn.execute("""
                SELECT
                    follower_id,
                    followee_id,
                    created_at
                FROM follow
                ORDER BY created_at DESC
            """)

            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # follow 表可能不存在
            return []

    def _get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        metadata = {
            "export_time": datetime.now().isoformat(),
            "database_path": self.db_path,
            "database_size": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
        }

        # 获取统计信息
        try:
            assert self.conn is not None
            # 用户统计
            metadata["user_count"] = self.conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]

            # 帖子统计
            metadata["post_count"] = self.conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]

            # 交互统计
            metadata["interaction_count"] = self.conn.execute("SELECT COUNT(*) FROM trace").fetchone()[0]

            # 时间范围
            time_range = self.conn.execute("""
                SELECT
                    MIN(created_at) as min_time,
                    MAX(created_at) as max_time
                FROM trace
            """).fetchone()

            if time_range[0] and time_range[1]:
                metadata["time_range"] = {
                    "start": time_range[0],
                    "end": time_range[1]
                }

        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to get metadata: {e}")
            metadata["error"] = str(e)

        return metadata

    # ========================================================================
    # 格式导出方法
    # ========================================================================

    def export_to_json(
        self, config: ExportConfig, output_path: str
    ) -> Dict[str, Any]:
        """
        导出为 JSON 格式

        Args:
            config: 导出配置
            output_path: 输出文件路径

        Returns:
            导出结果信息
        """
        try:
            start_time = time.time()

            # 获取数据
            data = self.get_all_data(config)

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            export_time = time.time() - start_time

            logger.info(f"Exported to JSON: {output_path} ({export_time:.2f}s)")

            return {
                "success": True,
                "format": "json",
                "file_path": output_path,
                "export_time": export_time,
                "record_count": sum(len(v) for v in data.values() if isinstance(v, list)),
            }

        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return {
                "success": False,
                "format": "json",
                "error": str(e),
            }

    def export_to_csv(
        self, config: ExportConfig, output_dir: str
    ) -> Dict[str, Any]:
        """
        导出为 CSV 格式（多个文件）

        Args:
            config: 导出配置
            output_dir: 输出目录路径

        Returns:
            导出结果信息
        """
        try:
            start_time = time.time()
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            files_created = []

            # 导出各个数据表
            if config.include_agents:
                self._export_table_to_csv("user", output_path / "users.csv")
                files_created.append("users.csv")

            if config.include_posts:
                self._export_table_to_csv("post", output_path / "posts.csv")
                files_created.append("posts.csv")

            if config.include_interactions:
                self._export_interactions_to_csv(output_path / "interactions.csv")
                files_created.append("interactions.csv")

            if config.include_comments:
                try:
                    self._export_table_to_csv("comment", output_path / "comments.csv")
                    files_created.append("comments.csv")
                except sqlite3.OperationalError:
                    logger.warning("Comment table not found, skipping")

            if config.include_follows:
                try:
                    self._export_table_to_csv("follow", output_path / "follows.csv")
                    files_created.append("follows.csv")
                except sqlite3.OperationalError:
                    logger.warning("Follow table not found, skipping")

            # 导出元数据
            metadata = self._get_metadata()
            with open(output_path / "metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
            files_created.append("metadata.json")

            export_time = time.time() - start_time

            logger.info(f"Exported to CSV: {output_dir} ({export_time:.2f}s)")

            return {
                "success": True,
                "format": "csv",
                "output_dir": str(output_dir),
                "files_created": files_created,
                "export_time": export_time,
            }

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return {
                "success": False,
                "format": "csv",
                "error": str(e),
            }

    def _export_table_to_csv(self, table_name: str, output_path: Path):
        """导出单个表到 CSV"""
        assert self.conn is not None
        cursor = self.conn.execute(f"SELECT * FROM {table_name}")
        columns = [description[0] for description in cursor.description]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()

            for row in cursor.fetchall():
                writer.writerow(dict(row))

    def _export_interactions_to_csv(self, output_path: Path):
        """导出交互数据到 CSV（处理 JSON info 字段）"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                user_id,
                created_at,
                action,
                info
            FROM trace
            ORDER BY created_at DESC
        """)

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "created_at", "action", "info"])

            for row in cursor.fetchall():
                user_id, created_at, action, info = row
                # 简化 JSON info 为字符串
                writer.writerow([user_id, created_at, action, info])

    # ========================================================================
    # 高级导出功能
    # ========================================================================

    def export_summary_statistics(self, output_path: str) -> Dict[str, Any]:
        """
        导出摘要统计信息

        Args:
            output_path: 输出文件路径

        Returns:
            统计信息字典
        """
        try:
            stats = {
                "user_stats": self._get_user_statistics(),
                "post_stats": self._get_post_statistics(),
                "interaction_stats": self._get_interaction_statistics(),
                "network_stats": self._get_network_statistics(),
                "temporal_stats": self._get_temporal_statistics(),
            }

            # 添加元数据
            stats["metadata"] = self._get_metadata()

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, default=str)

            logger.info(f"Exported summary statistics: {output_path}")

            return {
                "success": True,
                "file_path": output_path,
                "statistics": stats,
            }

        except Exception as e:
            logger.error(f"Failed to export statistics: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _get_user_statistics(self) -> Dict[str, Any]:
        """获取用户统计"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_users,
                AVG(num_followers) as avg_followers,
                AVG(num_followings) as avg_followings,
                MAX(num_followers) as max_followers
            FROM user
        """)

        return dict(cursor.fetchone())

    def _get_post_statistics(self) -> Dict[str, Any]:
        """获取帖子统计"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_posts,
                AVG(num_likes) as avg_likes,
                AVG(num_dislikes) as avg_dislikes,
                AVG(num_shares) as avg_shares
            FROM post
        """)

        return dict(cursor.fetchone())

    def _get_interaction_statistics(self) -> Dict[str, Any]:
        """获取交互统计"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                action,
                COUNT(*) as count
            FROM trace
            GROUP BY action
            ORDER BY count DESC
        """)

        return {"action_distribution": [dict(row) for row in cursor.fetchall()]}

    def _get_network_statistics(self) -> Dict[str, Any]:
        """获取网络统计"""
        try:
            assert self.conn is not None
            cursor = self.conn.execute("SELECT COUNT(*) FROM follow")
            follow_count = cursor.fetchone()[0]

            return {
                "total_follows": follow_count,
                "average_density": follow_count / max(1, self._get_user_count()),
            }
        except sqlite3.OperationalError:
            return {"total_follows": 0, "average_density": 0.0}

    def _get_temporal_statistics(self) -> Dict[str, Any]:
        """获取时间统计"""
        assert self.conn is not None
        cursor = self.conn.execute("""
            SELECT
                strftime('%Y-%m-%d', created_at) as date,
                COUNT(*) as count
            FROM trace
            GROUP BY date
            ORDER BY date
        """)

        return {"daily_activity": [dict(row) for row in cursor.fetchall()]}

    def _get_user_count(self) -> int:
        """获取用户数量"""
        assert self.conn is not None
        cursor = self.conn.execute("SELECT COUNT(*) FROM user")
        return cursor.fetchone()[0]


# ============================================================================
# 便捷函数
# ============================================================================

def export_oasis_data(
    db_path: str,
    export_format: str = "json",
    output_path: Optional[str] = None,
    include_agents: bool = True,
    include_posts: bool = True,
    include_interactions: bool = True,
) -> Dict[str, Any]:
    """
    导出 OASIS 数据的便捷函数

    Args:
        db_path: 数据库文件路径
        export_format: 导出格式 ("json" 或 "csv")
        output_path: 输出路径
        include_agents: 是否包含用户数据
        include_posts: 是否包含帖子数据
        include_interactions: 是否包含交互数据

    Returns:
        导出结果信息
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if export_format == "json":
            output_path = f"./data/exports/simulation_{timestamp}.json"
        else:
            output_path = f"./data/exports/simulation_{timestamp}/"

    config = ExportConfig(
        format=export_format,
        include_agents=include_agents,
        include_posts=include_posts,
        include_interactions=include_interactions,
    )

    with OASISDataExporter(db_path) as exporter:
        if export_format == "json":
            return exporter.export_to_json(config, output_path)
        else:
            return exporter.export_to_csv(config, output_path)
