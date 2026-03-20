"""
Metrics Analyzer for OASIS Dashboard

This module provides herd effect metrics calculation based on the OASIS paper:
- Reddit Hot Score algorithm for post ranking
- Herd effect measurement based on hot vs cold post behavior differences
- Replaces the old velocity and HHI metrics with paper-compliant implementations
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Reddit epoch timestamp (2005-12-08 07:46:43 UTC)
REDDIT_EPOCH = 1134028003


class MetricsAnalyzer:
    """
    羊群效应分析器（基于 OASIS 论文）

    功能：
    - 计算 Reddit 热度分数（Hot Score）
    - 分类热帖/冷帖
    - 计算热帖 vs 冷帖的行为差异
    - 缓存计算结果到数据库
    - 提供降级策略

    Reddit Hot Score 公式：
    h = log₁₀(max(|u-d|, 1)) + sign(u-d) × (t-t₀)/45000

    其中：
    - u: upvotes (点赞数)
    - d: downvotes (点踩数)
    - t: post creation timestamp
    - t₀: Reddit epoch (1134028003)
    """

    def __init__(self, db_path: str, cache_size: int = 1000):
        """
        初始化指标分析器

        Args:
            db_path: SQLite数据库路径
            cache_size: 缓存最近N条指标记录
        """
        self.db_path = db_path
        self.cache_size = cache_size
        self.last_herd_score = 0.0

        # 初始化数据库缓存表
        self._init_cache_table()

        logger.info(f"✅ 羊群效应分析器已初始化: cache_size={cache_size}")

    def _init_cache_table(self):
        """初始化指标缓存表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建缓存表（复用现有表结构）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_type TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_details TEXT,
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(metric_type, step_number)
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_type_step
                ON metrics_cache(metric_type, step_number)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_computed_at
                ON metrics_cache(computed_at)
            """)

            # 启用WAL模式以提高并发性能
            cursor.execute("PRAGMA journal_mode=WAL")

            conn.commit()
            conn.close()

            logger.debug("指标缓存表已初始化")

        except Exception as e:
            logger.error(f"初始化指标缓存表失败: {e}")

    def calculate_herd_effect_reddit(
        self,
        step_number: int,
        hot_threshold: float = 0.5,
        cold_threshold: float = 0.2,
        time_window_hours: float = 1.0,
    ) -> Dict:
        """
        基于 Reddit 热度公式的羊群效应分析

        Args:
            step_number: 当前步数
            hot_threshold: 热帖阈值（归一化热度分数 0-1）
            cold_threshold: 冷帖阈值
            time_window_hours: 分析时间窗口（小时）

        Returns:
            {
                'herd_effect_score': float,  # 羊群效应强度 0-1
                'hot_posts_count': int,
                'cold_posts_count': int,
                'hot_avg_engagement': float,
                'cold_avg_engagement': float,
                'behavior_difference': float,
                'post_scores': list,  # 所有帖子的热度分数（前10个）
                'step_number': int
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取时间窗口内的帖子
            cutoff_time = datetime.now().timestamp() - (time_window_hours * 3600)

            cursor.execute("""
                SELECT
                    p.post_id,
                    p.num_likes,
                    p.num_dislikes,
                    p.created_at,
                    COUNT(l.like_id) as actual_likes
                FROM post p
                LEFT JOIN like l ON p.post_id = l.post_id
                WHERE p.created_at >= datetime(? / 1000, 'unixepoch')
                GROUP BY p.post_id
                ORDER BY p.created_at DESC
                LIMIT 500
            """, (int(cutoff_time * 1000),))

            posts = cursor.fetchall()
            conn.close()

            if not posts:
                logger.warning(f"没有找到帖子数据，使用降级策略")
                return self._get_herd_fallback(error="no_posts")

            # 计算每个帖子的热度分数
            hot_scores = []
            for post_id, num_likes, num_dislikes, created_at, actual_likes in posts:
                # 使用实际点赞数（如果有的话）
                upvotes = actual_likes if actual_likes > 0 else (num_likes or 0)
                downvotes = num_dislikes or 0

                score = self._calculate_reddit_hot_score(
                    upvotes, downvotes, created_at
                )
                hot_scores.append({
                    'post_id': post_id,
                    'hot_score': score,
                    'upvotes': upvotes,
                    'downvotes': downvotes,
                })

            if not hot_scores:
                return self._get_herd_fallback(error="no_valid_scores")

            # 归一化热度分数到 0-1
            max_score = max(p['hot_score'] for p in hot_scores)
            min_score = min(p['hot_score'] for p in hot_scores)
            score_range = max_score - min_score if max_score != min_score else 1

            for post in hot_scores:
                post['normalized_score'] = (post['hot_score'] - min_score) / score_range

            # 分类热帖/冷帖
            hot_posts = [p for p in hot_scores if p['normalized_score'] >= hot_threshold]
            cold_posts = [p for p in hot_scores if p['normalized_score'] <= cold_threshold]

            # 计算行为差异
            hot_engagement = [
                p['upvotes'] + p['downvotes'] for p in hot_posts
            ]
            cold_engagement = [
                p['upvotes'] + p['downvotes'] for p in cold_posts
            ]

            hot_avg_engagement = sum(hot_engagement) / len(hot_engagement) if hot_engagement else 0
            cold_avg_engagement = sum(cold_engagement) / len(cold_engagement) if cold_engagement else 0

            behavior_diff = abs(hot_avg_engagement - cold_avg_engagement)
            behavior_diff_normalized = min(behavior_diff / 100.0, 1.0)  # 归一化到 0-1

            # 羊群效应分数：热帖越集中，羊群效应越强
            herd_score = len(hot_posts) / len(hot_scores) if hot_scores else 0

            result = {
                'herd_effect_score': round(herd_score, 4),
                'hot_posts_count': len(hot_posts),
                'cold_posts_count': len(cold_posts),
                'hot_avg_engagement': round(hot_avg_engagement, 2),
                'cold_avg_engagement': round(cold_avg_engagement, 2),
                'behavior_difference': round(behavior_diff_normalized, 4),
                'post_scores': hot_scores[:10],  # 只返回前10个用于展示
                'step_number': step_number,
            }

            # 缓存结果
            self._cache_metric("herd_effect_reddit", step_number, result)
            self.last_herd_score = result['herd_effect_score']

            logger.debug(
                f"羊群效应计算: step={step_number}, "
                f"herd_score={herd_score:.4f}, "
                f"hot={len(hot_posts)}, cold={len(cold_posts)}"
            )

            return result

        except Exception as e:
            logger.error(f"羊群效应计算失败: {e}")
            return self._get_herd_fallback(error=str(e))

    def _calculate_reddit_hot_score(
        self,
        upvotes: int,
        downvotes: int,
        created_at: str
    ) -> float:
        """
        计算 Reddit 热度分数

        公式：h = log₁₀(max(|u-d|, 1)) + sign(u-d) × (t-t₀)/45000

        Args:
            upvotes: 点赞数
            downvotes: 点踩数
            created_at: 创建时间 (ISO 8601 或 DATETIME 格式)

        Returns:
            热度分数
        """
        try:
            # 解析时间
            if isinstance(created_at, str):
                # 尝试多种时间格式
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                except ValueError:
                    # 尝试 SQLite datetime 格式
                    dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            else:
                dt = created_at

            timestamp = int(dt.timestamp())

            # 计算投票差
            vote_diff = upvotes - downvotes
            abs_vote_diff = abs(vote_diff)

            # 公式第一部分：log10(max(|u-d|, 1))
            log_part = math.log10(max(abs_vote_diff, 1))

            # 公式第二部分：sign(u-d) × (t-t₀)/45000
            sign = 1 if vote_diff > 0 else -1 if vote_diff < 0 else 0
            time_part = sign * (timestamp - REDDIT_EPOCH) / 45000

            hot_score = log_part + time_part

            return hot_score

        except Exception as e:
            logger.warning(f"热度分数计算失败: {e}, 返回 0.0")
            return 0.0

    def _cache_metric(self, metric_type: str, step_number: int, metric_data: Dict):
        """
        缓存指标到数据库

        Args:
            metric_type: 指标类型 ('herd_effect_reddit')
            step_number: 步数
            metric_data: 指标数据字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 提取主要值（第一个值）
            primary_value = list(metric_data.values())[0]
            if isinstance(primary_value, dict):
                primary_value = 0.0

            cursor.execute("""
                INSERT OR REPLACE INTO metrics_cache
                (metric_type, step_number, metric_value, metric_details)
                VALUES (?, ?, ?, ?)
            """, (
                metric_type,
                step_number,
                float(primary_value),
                json.dumps(metric_data, default=str)
            ))

            conn.commit()

            # 清理旧缓存（保留最近 N 条）
            cursor.execute("""
                DELETE FROM metrics_cache
                WHERE id NOT IN (
                    SELECT id FROM metrics_cache
                    ORDER BY computed_at DESC
                    LIMIT ?
                )
            """, (self.cache_size,))

            conn.commit()
            conn.close()

            logger.debug(f"已缓存 {metric_type} 指标 (step={step_number})")

        except Exception as e:
            logger.error(f"缓存指标失败: {e}")

    def get_cached_herd_effect(self, step_number: int) -> Dict:
        """
        获取缓存的羊群效应指标

        Args:
            step_number: 步数

        Returns:
            羊群效应指标字典
        """
        return self._get_cached_metric("herd_effect_reddit", step_number)

    def _get_cached_metric(self, metric_type: str, step_number: int) -> Dict:
        """从缓存读取指标"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT metric_details FROM metrics_cache
                WHERE metric_type = ? AND step_number = ?
                ORDER BY computed_at DESC
                LIMIT 1
            """, (metric_type, step_number))

            row = cursor.fetchone()
            conn.close()

            if row:
                return json.loads(row[0])

            return {}

        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")
            return {}

    def _get_herd_fallback(self, error: str = None) -> Dict:
        """
        羊群效应计算失败时的降级策略

        Args:
            error: 错误信息

        Returns:
            降级结果
        """
        return {
            "herd_effect_score": self.last_herd_score if hasattr(self, 'last_herd_score') else 0.0,
            "error": error,
            "degraded": True
        }

    def get_latest_metrics(self, step_number: int) -> Dict:
        """
        获取指定步骤的所有指标（从缓存）

        Args:
            step_number: 步数

        Returns:
            {
                'herd_effect_reddit': dict
            }
        """
        return {
            "herd_effect_reddit": self.get_cached_herd_effect(step_number)
        }
