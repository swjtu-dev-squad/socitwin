"""
Propagation Analyzer for OASIS Dashboard

This module provides information propagation metrics as defined in the OASIS paper:
- Scale: Number of unique users participating in propagation
- Depth: Maximum distance from root in the propagation graph
- Max Breadth: Maximum number of participants at any depth level
- NRMSE: Normalized RMSE compared with real-world data (optional)
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PropagationMetrics:
    """Data class for propagation metrics."""
    scale: int  # Number of unique users
    depth: int  # Maximum depth of propagation
    max_breadth: int  # Maximum breadth at any depth
    num_trees: int  # Number of propagation trees (cascades)
    nrmse: Optional[float] = None  # NRMSE if real data available
    round_number: int = 0
    step_range: Tuple[int, int] = (0, 0)


@dataclass
class TreeNode:
    """Node in the propagation tree."""
    post_id: int
    user_id: int
    parent_id: Optional[int] = None  # original_post_id
    depth: int = 0
    children: List[int] = field(default_factory=list)


class PropagationAnalyzer:
    """
    信息传播分析器

    计算 OASIS 论文中定义的传播指标：
    - Scale: 参与传播的唯一用户数
    - Depth: 传播图的最大深度
    - Max Breadth: 任一深度的最大用户数
    - NRMSE: 与现实数据的归一化 RMSE（可选）

    功能：
    - 构建传播树（使用 post.original_post_id）
    - BFS 计算深度和宽度
    - 缓存计算结果
    - 支持与现实数据对比
    """

    def __init__(
        self,
        db_path: str,
        cache_size: int = 1000,
        round_duration_steps: int = 10,
        enable_nrmse: bool = False,
        real_data_path: Optional[str] = None,
    ):
        """
        初始化传播分析器

        Args:
            db_path: SQLite 数据库路径
            cache_size: 缓存最近 N 条记录
            round_duration_steps: 一个 round 包含多少 steps
            enable_nrmse: 是否启用 NRMSE 计算（需要真实数据）
            real_data_path: 真实传播数据文件路径（JSON 格式）
        """
        self.db_path = db_path
        self.cache_size = cache_size
        self.round_duration_steps = round_duration_steps
        self.enable_nrmse = enable_nrmse
        self.real_data = self._load_real_data(real_data_path) if enable_nrmse else None

        # 缓存
        self._cache: Dict[int, PropagationMetrics] = {}

        # 初始化数据库表
        self._init_cache_table()

        logger.info(
            f"✅ 传播分析器已初始化: cache_size={cache_size}, "
            f"round_duration={round_duration_steps}, enable_nrmse={enable_nrmse}"
        )

    def _init_cache_table(self):
        """初始化缓存表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS propagation_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_number INTEGER NOT NULL UNIQUE,
                    scale INTEGER NOT NULL,
                    depth INTEGER NOT NULL,
                    max_breadth INTEGER NOT NULL,
                    nrmse REAL,
                    graph_summary TEXT,
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_propagation_round
                ON propagation_cache(round_number)
            """)

            # 启用 WAL 模式
            cursor.execute("PRAGMA journal_mode=WAL")

            conn.commit()
            conn.close()

            logger.debug("传播缓存表已初始化")

        except Exception as e:
            logger.error(f"初始化缓存表失败: {e}")

    def _load_real_data(self, path: Optional[str]) -> Optional[Dict]:
        """
        加载真实传播数据用于 NRMSE 计算

        Args:
            path: JSON 文件路径

        Returns:
            真实数据字典，格式：{round_number: {scale, depth, max_breadth}}
        """
        if not path or not Path(path).exists():
            logger.warning(f"真实数据文件不存在: {path}")
            return None

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            # 转换为 {round_number: metrics} 格式
            real_data = {}
            for round_data in data.get('rounds', []):
                round_num = round_data['round']
                real_data[round_num] = round_data['metrics']

            logger.info(f"已加载真实传播数据: {len(real_data)} rounds")
            return real_data

        except Exception as e:
            logger.error(f"加载真实数据失败: {e}")
            return None

    async def analyze_round(self, round_number: int) -> Dict:
        """
        分析指定 round 的传播指标

        Args:
            round_number: Round 编号（从 1 开始）

        Returns:
            {
                'scale': int,
                'depth': int,
                'max_breadth': int,
                'round': int,
                'nrmse': float (optional),
                'step_range': (start_step, end_step)
            }
        """
        try:
            # 计算 round 对应的 step 范围
            start_step = (round_number - 1) * self.round_duration_steps + 1
            end_step = round_number * self.round_duration_steps

            # 构建传播图
            graph_data = self._build_propagation_graph(start_step, end_step)

            # 计算 NRMSE（如果启用）
            nrmse = None
            if self.enable_nrmse and self.real_data:
                nrmse = self._calculate_nrmse(
                    round_number,
                    graph_data['scale'],
                    graph_data['depth'],
                    graph_data['max_breadth']
                )

            # 创建结果对象
            metrics = PropagationMetrics(
                scale=graph_data['scale'],
                depth=graph_data['depth'],
                max_breadth=graph_data['max_breadth'],
                num_trees=graph_data['num_trees'],
                nrmse=nrmse,
                round_number=round_number,
                step_range=(start_step, end_step)
            )

            # 缓存结果
            self._cache[round_number] = metrics
            self._save_to_cache(metrics)

            logger.info(
                f"✅ Round {round_number} 传播分析完成: "
                f"scale={metrics.scale}, depth={metrics.depth}, "
                f"max_breadth={metrics.max_breadth}"
            )

            return {
                'scale': metrics.scale,
                'depth': metrics.depth,
                'max_breadth': metrics.max_breadth,
                'round': round_number,
                'nrmse': nrmse,
                'num_trees': metrics.num_trees,
                'step_range': (start_step, end_step)
            }

        except Exception as e:
            logger.error(f"Round {round_number} 传播分析失败: {e}")
            return {
                'scale': 0,
                'depth': 0,
                'max_breadth': 0,
                'round': round_number,
                'error': str(e)
            }

    def _build_propagation_graph(
        self,
        start_step: int,
        end_step: int
    ) -> Dict[str, Any]:
        """
        构建传播图并计算指标

        算法：
        1. 查询 step 范围内的所有帖子
        2. 使用 original_post_id 构建父子关系
        3. BFS 计算每个根节点的深度和宽度
        4. 聚合计算全局指标

        Args:
            start_step: 起始 step
            end_step: 结束 step

        Returns:
            {
                'scale': int,
                'depth': int,
                'max_breadth': int,
                'num_trees': int
            }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 注意：这里使用 post_id 范围近似 step 范围
        # 实际生产环境应使用 step 字段或 created_at 时间范围
        cursor.execute("""
            SELECT
                p.post_id,
                p.user_id,
                p.original_post_id,
                p.created_at
            FROM post p
            WHERE p.post_id BETWEEN ? AND ?
            ORDER BY p.post_id ASC
        """, (start_step, end_step * 100))  # 放大范围以获取足够数据

        posts = cursor.fetchall()

        if not posts:
            conn.close()
            return {'scale': 0, 'depth': 0, 'max_breadth': 0, 'num_trees': 0}

        # 构建节点映射
        nodes = {}  # post_id -> TreeNode
        root_nodes = []

        for post_id, user_id, original_post_id, created_at in posts:
            node = TreeNode(
                post_id=post_id,
                user_id=user_id,
                parent_id=original_post_id
            )
            nodes[post_id] = node

            if original_post_id is None:
                # 根节点（原创帖子）
                root_nodes.append(post_id)
            else:
                # 子节点（分享/转发）
                if original_post_id in nodes:
                    nodes[original_post_id].children.append(post_id)

        conn.close()

        if not nodes:
            return {'scale': 0, 'depth': 0, 'max_breadth': 0, 'num_trees': 0}

        # BFS 计算每个树的深度和宽度
        max_depth = 0
        max_breadth = 0
        unique_users = set()

        for root_id in root_nodes:
            if root_id not in nodes:
                continue

            # BFS
            queue = deque([(root_id, 0)])
            depth_counts = defaultdict(int)
            visited = set()

            while queue:
                node_id, depth = queue.popleft()

                if node_id in visited:
                    continue
                visited.add(node_id)

                node = nodes.get(node_id)
                if not node:
                    continue

                unique_users.add(node.user_id)
                depth_counts[depth] += 1

                # 更新深度
                max_depth = max(max_depth, depth)

                # 添加子节点
                for child_id in node.children:
                    if child_id not in visited:
                        queue.append((child_id, depth + 1))

            # 更新宽度
            tree_max_breadth = max(depth_counts.values()) if depth_counts else 0
            max_breadth = max(max_breadth, tree_max_breadth)

        return {
            'scale': len(unique_users),
            'depth': max_depth,
            'max_breadth': max_breadth,
            'num_trees': len(root_nodes)
        }

    def _calculate_nrmse(
        self,
        round_number: int,
        scale: int,
        depth: int,
        max_breadth: int
    ) -> float:
        """
        计算归一化 RMSE（与真实数据对比）

        NRMSE = sqrt(mean((sim - real)^2)) / range

        Args:
            round_number: Round 编号
            scale: 模拟的规模
            depth: 模拟的深度
            max_breadth: 模拟的最大宽度

        Returns:
            NRMSE 值（0-1），如果无真实数据则返回 0.0
        """
        if not self.real_data or round_number not in self.real_data:
            return 0.0

        try:
            real = self.real_data[round_number]

            # 计算各指标的误差
            errors = [
                (scale - real.get('scale', 0)) ** 2,
                (depth - real.get('depth', 0)) ** 2,
                (max_breadth - real.get('max_breadth', 0)) ** 2,
            ]

            # MSE
            mse = sum(errors) / len(errors)

            # RMSE
            rmse = math.sqrt(mse)

            # 归一化：计算真实数据的范围
            real_values = [
                real.get('scale', 0),
                real.get('depth', 0),
                real.get('max_breadth', 0)
            ]
            range_val = max(real_values) - min(real_values)

            if range_val == 0:
                return 0.0

            nrmse = rmse / range_val

            logger.debug(
                f"NRMSE (Round {round_number}): {nrmse:.4f} "
                f"(sim=[{scale},{depth},{max_breadth}], "
                f"real=[{real.get('scale',0)},{real.get('depth',0)},{real.get('max_breadth',0)}])"
            )

            return round(nrmse, 4)

        except Exception as e:
            logger.error(f"NRMSE 计算失败: {e}")
            return 0.0

    def _save_to_cache(self, metrics: PropagationMetrics):
        """
        保存传播指标到数据库缓存

        Args:
            metrics: 传播指标对象
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            graph_summary = json.dumps({
                'num_trees': metrics.num_trees,
                'step_range': metrics.step_range,
            })

            cursor.execute("""
                INSERT OR REPLACE INTO propagation_cache
                (round_number, scale, depth, max_breadth, nrmse, graph_summary, computed_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                metrics.round_number,
                metrics.scale,
                metrics.depth,
                metrics.max_breadth,
                metrics.nrmse,
                graph_summary
            ))

            # 清理旧缓存
            cursor.execute("""
                DELETE FROM propagation_cache
                WHERE id NOT IN (
                    SELECT id FROM propagation_cache
                    ORDER BY computed_at DESC
                    LIMIT ?
                )
            """, (self.cache_size,))

            conn.commit()
            conn.close()

            logger.debug(f"已缓存 Round {metrics.round_number} 传播指标")

        except Exception as e:
            logger.error(f"保存缓存失败: {e}")

    def get_cached_round(self, round_number: int) -> Dict:
        """
        获取缓存的传播指标

        Args:
            round_number: Round 编号

        Returns:
            传播指标字典
        """
        # 先查内存缓存
        if round_number in self._cache:
            metrics = self._cache[round_number]
            return {
                'scale': metrics.scale,
                'depth': metrics.depth,
                'max_breadth': metrics.max_breadth,
                'round': round_number,
                'nrmse': metrics.nrmse,
                'cached': True
            }

        # 查数据库缓存
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT scale, depth, max_breadth, nrmse
                FROM propagation_cache
                WHERE round_number = ?
            """, (round_number,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'scale': row[0],
                    'depth': row[1],
                    'max_breadth': row[2],
                    'round': round_number,
                    'nrmse': row[3],
                    'cached': True
                }

        except Exception as e:
            logger.warning(f"读取缓存失败: {e}")

        # 返回降级值
        return {
            'scale': 0,
            'depth': 0,
            'max_breadth': 0,
            'round': round_number,
            'cached': False
        }

    def clear_cache(self):
        """清空所有缓存"""
        self._cache.clear()
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM propagation_cache")
            conn.commit()
            conn.close()
            logger.info("传播缓存已清空")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")
