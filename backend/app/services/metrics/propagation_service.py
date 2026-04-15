"""
Propagation Service - Information propagation metrics calculation

This service calculates how information spreads through the social network
using recursive SQL CTEs to build propagation trees.
"""

import logging
import sqlite3
from typing import Any, Dict, List, Optional

from app.models.metrics import PropagationMetrics

logger = logging.getLogger(__name__)


class PropagationService:
    """
    Calculate information propagation metrics

    Measures how information (posts) spreads through the social network
    by analyzing repost/quote chains and user participation.
    """

    def __init__(self, db_path: str):
        """
        Initialize propagation service

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        logger.info(f"PropagationService initialized with db: {db_path}")

    async def get_metrics(
        self,
        post_id: Optional[int] = None
    ) -> PropagationMetrics:
        """
        Get propagation metrics

        Args:
            post_id: Specific post ID to analyze, or None for aggregate metrics

        Returns:
            PropagationMetrics object with scale, depth, and max_breadth

        Raises:
            ValueError: If post_id not found or is not an original post
            sqlite3.Error: If database query fails
        """
        try:
            if post_id:
                return await self._calculate_single_post_propagation(post_id)
            else:
                return await self._calculate_aggregate_propagation()

        except Exception as e:
            logger.error(f"Failed to calculate propagation metrics: {e}")
            raise

    async def _calculate_single_post_propagation(
        self,
        post_id: int
    ) -> PropagationMetrics:
        """
        Calculate propagation for a single post

        Uses recursive CTE to build propagation tree and calculate metrics.

        Args:
            post_id: Original post ID to analyze

        Returns:
            PropagationMetrics for the specific post
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Verify post exists and is original
            cursor.execute("""
                SELECT original_post_id
                FROM post
                WHERE post_id = ?
            """, (post_id,))

            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Post {post_id} not found")

            if result['original_post_id'] is not None:
                raise ValueError(
                    f"Post {post_id} is not an original post "
                    f"(original_post_id={result['original_post_id']})"
                )

            # Build propagation tree using recursive CTE
            cursor.execute("""
                WITH RECURSIVE propagation_tree AS (
                    -- Base case: root post
                    SELECT
                        post_id,
                        user_id,
                        original_post_id,
                        0 as depth
                    FROM post
                    WHERE post_id = ? AND original_post_id IS NULL

                    UNION ALL

                    -- Recursive case: shared posts (reposts, quotes)
                    SELECT
                        p.post_id,
                        p.user_id,
                        p.original_post_id,
                        pt.depth + 1
                    FROM post p
                    JOIN propagation_tree pt ON p.original_post_id = pt.post_id
                    WHERE pt.depth < 100  -- Prevent infinite loops
                )
                SELECT
                    depth,
                    COUNT(DISTINCT user_id) as users_at_depth,
                    COUNT(DISTINCT post_id) as posts_at_depth
                FROM propagation_tree
                GROUP BY depth
                ORDER BY depth;
            """, (post_id,))

            rows = cursor.fetchall()

            if not rows:
                # Post has no shares
                logger.info(f"Post {post_id} has no propagation (no shares)")
                return PropagationMetrics(
                    scale=1,
                    depth=0,
                    max_breadth=1,
                    post_id=post_id
                )

            # Calculate metrics
            total_unique_users = sum(row['users_at_depth'] for row in rows)
            max_depth = max(row['depth'] for row in rows)
            max_breadth = max(row['users_at_depth'] for row in rows)

            logger.info(
                f"Propagation metrics for post {post_id}: "
                f"scale={total_unique_users}, depth={max_depth}, "
                f"max_breadth={max_breadth}"
            )

            return PropagationMetrics(
                scale=total_unique_users,
                depth=max_depth,
                max_breadth=max_breadth,
                post_id=post_id
            )

    async def _calculate_aggregate_propagation(
        self
    ) -> PropagationMetrics:
        """
        Calculate aggregate propagation across all posts

        Calculates average propagation metrics across all original posts.

        Returns:
            PropagationMetrics averaged across all posts
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get all original posts
            cursor.execute("""
                SELECT post_id
                FROM post
                WHERE original_post_id IS NULL
                ORDER BY post_id
            """)

            original_posts = cursor.fetchall()

            if not original_posts:
                logger.info("No original posts found")
                return PropagationMetrics(
                    scale=0,
                    depth=0,
                    max_breadth=0,
                    post_id=None
                )

            # Calculate propagation for each original post
            scales = []
            depths = []
            breadths = []

            for post_row in original_posts:
                post_id = post_row['post_id']
                try:
                    metrics = await self._calculate_single_post_propagation(post_id)
                    scales.append(metrics.scale)
                    depths.append(metrics.depth)
                    breadths.append(metrics.max_breadth)
                except Exception as e:
                    logger.warning(f"Failed to calculate propagation for post {post_id}: {e}")
                    continue

            if not scales:
                logger.info("No valid propagation metrics calculated")
                return PropagationMetrics(
                    scale=0,
                    depth=0,
                    max_breadth=0,
                    post_id=None
                )

            # Calculate averages
            avg_scale = sum(scales) / len(scales)
            avg_depth = sum(depths) / len(depths)
            avg_breadth = sum(breadths) / len(breadths)

            logger.info(
                f"Aggregate propagation: scale={avg_scale:.2f}, "
                f"depth={avg_depth:.2f}, breadth={avg_breadth:.2f} "
                f"(from {len(scales)} posts)"
            )

            return PropagationMetrics(
                scale=int(avg_scale),
                depth=int(avg_depth),
                max_breadth=int(avg_breadth),
                post_id=None
            )

    async def get_propagation_tree(
        self,
        post_id: int,
        max_depth: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get detailed propagation tree for a post

        Args:
            post_id: Original post ID
            max_depth: Maximum depth to traverse

        Returns:
            List of nodes in propagation tree with structure:
            [{
                'post_id': int,
                'user_id': int,
                'depth': int,
                'parent_id': Optional[int]
            }]
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                WITH RECURSIVE propagation_tree AS (
                    SELECT
                        p.post_id,
                        p.user_id,
                        p.original_post_id as parent_id,
                        0 as depth
                    FROM post p
                    WHERE p.post_id = ? AND p.original_post_id IS NULL

                    UNION ALL

                    SELECT
                        p.post_id,
                        p.user_id,
                        p.original_post_id as parent_id,
                        pt.depth + 1
                    FROM post p
                    JOIN propagation_tree pt ON p.original_post_id = pt.post_id
                    WHERE pt.depth < ?
                )
                SELECT
                    post_id,
                    user_id,
                    parent_id,
                    depth
                FROM propagation_tree
                ORDER BY depth, post_id;
            """, (post_id, max_depth))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]
