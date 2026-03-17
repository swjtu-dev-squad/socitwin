"""
Metrics Analyzer for OASIS Dashboard

This module provides system behavior metrics calculation including:
- Information velocity (posts per second)
- Herd effect index (normalized HHI based on action distribution)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict

logger = logging.getLogger(__name__)


class MetricsAnalyzer:
    """
    系统行为指标分析器

    功能：
    - 计算信息传播速度 (Δposts/Δtime)
    - 计算羊群效应指数（归一化 HHI）
    - 缓存计算结果到数据库
    - 提供降级策略
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
        self.last_velocity = 0.0
        self.last_hhi = 0.0

        # 初始化数据库缓存表
        self._init_cache_table()

        logger.info(f"✅ 指标分析器已初始化: cache_size={cache_size}")

    def _init_cache_table(self):
        """初始化指标缓存表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建缓存表
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

    def calculate_velocity(
        self,
        step_number: int,
        current_posts: int,
        previous_posts: int,
        step_duration_s: float
    ) -> Dict:
        """
        计算信息传播速度

        Args:
            step_number: 当前步数
            current_posts: 当前帖子总数
            previous_posts: 上一步帖子总数
            step_duration_s: 步骤持续时间（秒）

        Returns:
            {
                'velocity': float,  # posts per second
                'delta_posts': int,
                'step_duration': float,
                'step_number': int
            }
        """
        # 边界情况处理
        if step_duration_s <= 0:
            return {
                "velocity": 0.0,
                "error": "invalid_time_delta",
                "step_number": step_number
            }

        delta_posts = current_posts - previous_posts
        velocity = delta_posts / step_duration_s

        result = {
            "velocity": round(velocity, 4),
            "delta_posts": delta_posts,
            "step_duration": round(step_duration_s, 4),
            "step_number": step_number
        }

        # 缓存结果
        self._cache_metric("velocity", step_number, result)
        self.last_velocity = result["velocity"]

        logger.debug(
            f"速度计算: step={step_number}, velocity={velocity:.4f} posts/s, "
            f"delta_posts={delta_posts}"
        )

        return result

    def calculate_herd_hhi(
        self,
        step_number: int,
        time_window_s: float = 60.0
    ) -> Dict:
        """
        计算羊群效应指数（归一化 HHI）

        Args:
            step_number: 当前步数
            time_window_s: 分析时间窗口（秒），默认60秒

        Returns:
            {
                'herd_hhi': float,  # 归一化 HHI (0-1)
                'raw_hhi': float,   # 原始 HHI
                'action_distribution': dict,  # action -> proportion
                'n_action_types': int,
                'total_actions': int,
                'time_window_s': float,
                'step_number': int
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取时间窗口内的 action 分布
            cutoff_time = (datetime.now() - timedelta(seconds=time_window_s)).isoformat()

            cursor.execute("""
                SELECT action, COUNT(*) as count
                FROM trace
                WHERE created_at >= ?
                GROUP BY action
                ORDER BY count DESC
            """, (cutoff_time,))

            actions = cursor.fetchall()
            conn.close()

            if not actions:
                logger.warning(f"没有找到 trace 数据，使用降级策略")
                return self._get_herd_fallback(error="no_trace_data")

            # 计算 HHI
            total_actions = sum(count for _, count in actions)
            action_distribution = {action: count / total_actions for action, count in actions}

            # 原始 HHI: Σ(p_a)²
            raw_hhi = sum(p ** 2 for p in action_distribution.values())
            n_actions = len(action_distribution)

            # 归一化 HHI (消除类别数量影响)
            # H_norm = (H - 1/n) / (1 - 1/n)
            if n_actions > 1:
                normalized_hhi = (raw_hhi - 1 / n_actions) / (1 - 1 / n_actions)
            else:
                # 只有一个 action 类型，完全集中
                normalized_hhi = 1.0

            result = {
                "herd_hhi": round(normalized_hhi, 4),
                "raw_hhi": round(raw_hhi, 4),
                "action_distribution": {
                    k: round(v, 4) for k, v in action_distribution.items()
                },
                "n_action_types": n_actions,
                "total_actions": total_actions,
                "time_window_s": time_window_s,
                "step_number": step_number
            }

            # 缓存结果
            self._cache_metric("herd_hhi", step_number, result)
            self.last_hhi = result["herd_hhi"]

            logger.debug(
                f"HHI 计算: step={step_number}, herd_hhi={normalized_hhi:.4f}, "
                f"actions={n_actions}, total={total_actions}"
            )

            return result

        except Exception as e:
            logger.error(f"HHI 计算失败: {e}")
            return self._get_herd_fallback(error=str(e))

    def _cache_metric(self, metric_type: str, step_number: int, metric_data: Dict):
        """
        缓存指标到数据库

        Args:
            metric_type: 指标类型 ('velocity' 或 'herd_hhi')
            step_number: 步数
            metric_data: 指标数据字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 提取主要值（字典的第一个值）
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

    def get_cached_velocity(self, step_number: int) -> Dict:
        """获取缓存的速度指标"""
        return self._get_cached_metric("velocity", step_number)

    def get_cached_hhi(self, step_number: int) -> Dict:
        """获取缓存的 HHI 指标"""
        return self._get_cached_metric("herd_hhi", step_number)

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
        HHI 计算失败时的降级策略

        Args:
            error: 错误信息

        Returns:
            降级结果
        """
        return {
            "herd_hhi": self.last_hhi if hasattr(self, 'last_hhi') else 0.0,
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
                'velocity': dict,
                'herd_hhi': dict
            }
        """
        return {
            "velocity": self.get_cached_velocity(step_number),
            "herd_hhi": self.get_cached_hhi(step_number)
        }
