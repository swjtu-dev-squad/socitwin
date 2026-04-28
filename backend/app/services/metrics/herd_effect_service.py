"""
Herd Effect Service - Herd behavior and conformity metrics

This service calculates herd effect metrics including:
- Post scores (likes - dislikes)
- Reddit hot formula for time-decayed popularity
- Conformity index using Gini coefficient
"""

import logging
import math
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.metrics import HerdEffectMetrics, HotPost

logger = logging.getLogger(__name__)


class HerdEffectService:
    """
    Calculate herd effect metrics

    Measures conformity and popularity-biased behavior patterns
    using engagement metrics and distribution analysis.
    """

    def __init__(self, db_path: str):
        """
        Initialize herd effect service

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        logger.info(f"HerdEffectService initialized with db: {db_path}")

    async def get_metrics(
        self,
        time_window: Optional[timedelta] = None
    ) -> HerdEffectMetrics:
        """
        Get herd effect metrics

        Args:
            time_window: Optional time window for analysis

        Returns:
            HerdEffectMetrics with scores, disagreement, and conformity

        Raises:
            sqlite3.Error: If database query fails
        """
        try:
            # Calculate post scores
            post_scores = await self._calculate_post_scores(time_window)

            if not post_scores:
                logger.info("No posts found for herd effect analysis")
                return HerdEffectMetrics(
                    average_post_score=0.0,
                    disagree_score=0.0,
                    hot_posts=[],
                    conformity_index=0.0
                )

            # Calculate average post score
            avg_score = sum(
                p['net_score'] for p in post_scores
            ) / len(post_scores)

            # Calculate disagreement score (opinion variance)
            disagree_score = self._calculate_disagreement(post_scores)

            # Calculate hot posts using Reddit formula
            hot_posts = await self._calculate_hot_posts(post_scores)

            # Calculate conformity index (Gini coefficient)
            conformity_index = self._calculate_conformity_index(post_scores)

            logger.info(
                f"Herd effect metrics: avg_score={avg_score:.2f}, "
                f"disagree={disagree_score:.2f}, conformity={conformity_index:.2f}"
            )

            return HerdEffectMetrics(
                average_post_score=avg_score,
                disagree_score=disagree_score,
                hot_posts=hot_posts[:10],  # Top 10
                conformity_index=conformity_index
            )

        except Exception as e:
            logger.error(f"Failed to calculate herd effect metrics: {e}")
            raise

    async def _calculate_post_scores(
        self,
        time_window: Optional[timedelta]
    ) -> List[Dict[str, Any]]:
        """
        Calculate post scores (likes - dislikes)

        Args:
            time_window: Optional time window filter

        Returns:
            List of posts with engagement metrics
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if time_window:
                cursor.execute("""
                    SELECT
                        post_id,
                        user_id,
                        content,
                        num_likes,
                        num_dislikes,
                        num_shares,
                        created_at,
                        (num_likes - num_dislikes) as net_score
                    FROM post
                    WHERE datetime(created_at) >= datetime('now', '-' || ? || ' seconds')
                    ORDER BY net_score DESC
                """, (int(time_window.total_seconds()),))
            else:
                cursor.execute("""
                    SELECT
                        post_id,
                        user_id,
                        content,
                        num_likes,
                        num_dislikes,
                        num_shares,
                        created_at,
                        (num_likes - num_dislikes) as net_score
                    FROM post
                    ORDER BY net_score DESC
                """)

            return [dict(row) for row in cursor.fetchall()]

    def _calculate_disagreement(
        self,
        post_scores: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate disagreement score (opinion variance)

        Uses standard deviation of post scores as proxy for disagreement.

        Args:
            post_scores: List of posts with net_score field

        Returns:
            Disagreement score (standard deviation)
        """
        if len(post_scores) < 2:
            return 0.0

        scores = [p['net_score'] for p in post_scores]
        mean = sum(scores) / len(scores)

        # Calculate variance
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        return math.sqrt(variance)  # Standard deviation

    async def _calculate_hot_posts(
        self,
        post_scores: List[Dict[str, Any]]
    ) -> List[HotPost]:
        """
        Calculate Reddit-style hot scores

        Reddit hot formula:
        h = log₁₀(|likes-dislikes|) + sign(likes-dislikes) × (t-t₀)/45000

        Args:
            post_scores: List of posts with engagement data

        Returns:
            List of HotPost objects sorted by hot score
        """
        hot_posts = []

        # Reddit epoch (constant)
        reddit_epoch = 1134028003  # Unix timestamp

        for post in post_scores:
            net_score = post['net_score']
            abs_score = abs(net_score)

            # Logarithmic score
            if abs_score == 0:
                log_score = 0
            else:
                log_score = math.log10(abs_score)

            # Time decay (45,000 seconds = 12.5 hours)
            try:
                # Handle different datetime formats
                created_at = post['created_at']

                if isinstance(created_at, (int, float)):
                    # Unix timestamp
                    post_time = datetime.fromtimestamp(created_at)
                elif isinstance(created_at, str):
                    try:
                        # ISO format string
                        post_time = datetime.fromisoformat(created_at)
                    except ValueError:
                        # Legacy datetime format
                        post_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                else:
                    # Fallback to current time
                    logger.warning(f"Unexpected datetime format: {type(created_at)}, using current time")
                    post_time = datetime.now()
            except Exception as e:
                logger.warning(f"Failed to parse datetime: {e}, using current time")
                post_time = datetime.now()

            (datetime.now() - post_time).total_seconds()

            sign = 1 if net_score >= 0 else -1
            hot_score = log_score + sign * ((post_time.timestamp() - reddit_epoch) / 45000)

            hot_posts.append(HotPost(
                post_id=post['post_id'],
                user_id=post['user_id'],
                content=post['content'][:100],  # Truncate for display
                net_score=net_score,
                hot_score=hot_score,
                created_at=post_time
            ))

        # Sort by hot score
        hot_posts.sort(key=lambda x: x.hot_score, reverse=True)
        return hot_posts

    def _calculate_conformity_index(
        self,
        post_scores: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate conformity index using Gini coefficient

        Measures inequality in engagement distribution.
        0 = perfectly equal (no herd), 1 = maximum inequality (strong herd)

        Args:
            post_scores: List of posts with net_score field

        Returns:
            Conformity index (0-1)
        """
        if not post_scores:
            return 0.0

        # Sort by absolute score
        scores = sorted([abs(p['net_score']) for p in post_scores])
        n = len(scores)

        if n == 0:
            return 0.0

        # Calculate Gini coefficient using Lorenz curve
        cumulative_scores = []
        sum_scores = 0

        for score in scores:
            sum_scores += score
            cumulative_scores.append(sum_scores)

        # Area under Lorenz curve
        if sum_scores == 0:
            return 0.0

        area_under_lorenz = sum(
            cs / (sum_scores * n) for cs in cumulative_scores
        )

        # Gini coefficient
        gini = 1 - 2 * area_under_lorenz

        # Ensure result is in [0, 1]
        return max(0.0, min(1.0, gini))
