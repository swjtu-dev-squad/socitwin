import json
import logging
import sqlite3

from app.models.metrics import SentimentAnalyzedPost, SentimentTendencyMetrics
from app.services.proxy_service import proxy_service
from app.utils import metrics_db

logger = logging.getLogger(__name__)


class SentimentTendencyService:
    """Calculate per-step sentiment tendency from newly created posts."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_metrics(self) -> SentimentTendencyMetrics:
        last_processed_post_id = self._get_last_processed_post_id()
        posts = self._get_new_posts(last_processed_post_id)

        analyzed_posts: list[SentimentAnalyzedPost] = []
        signed_sum = 0.0
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for post in posts:
            try:
                analysis_payload = await proxy_service.classify_sentiment(post["content"] or "")
                prediction = analysis_payload.get("analysis", {}).get("prediction", {})
                final_result = analysis_payload.get("final_result", "中性")
                confidence = float(prediction.get("confidence", 0.0) or 0.0)
            except Exception as exc:
                logger.warning(
                    "Skipping post %s for sentiment tendency due to analysis failure: %s",
                    post.get("post_id"),
                    exc,
                )
                continue

            if final_result == "正向":
                signed_score = confidence
                positive_count += 1
                signed_sum += signed_score
            elif final_result == "负向":
                signed_score = -confidence
                negative_count += 1
                signed_sum += signed_score
            else:
                signed_score = 0.0
                neutral_count += 1

            analyzed_posts.append(
                SentimentAnalyzedPost(
                    post_id=post["post_id"],
                    user_id=post["user_id"],
                    sentiment=final_result,
                    confidence=confidence,
                    signed_score=signed_score,
                )
            )

        non_neutral_count = positive_count + negative_count
        overall_score = signed_sum / non_neutral_count if non_neutral_count > 0 else 0.0
        last_post_id = posts[-1]["post_id"] if posts else last_processed_post_id

        return SentimentTendencyMetrics(
            overall_score=overall_score,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            analyzed_post_count=len(posts),
            non_neutral_count=non_neutral_count,
            last_post_id=last_post_id,
            posts=analyzed_posts,
        )

    def _get_new_posts(self, last_processed_post_id: int) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT post_id, user_id, content
                FROM post
                WHERE post_id > ?
                ORDER BY post_id ASC
                """,
                (last_processed_post_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_last_processed_post_id(self) -> int:
        latest = metrics_db.get_latest_metrics(self.db_path, "sentiment_tendency")
        if not latest:
            return 0

        metric_data = latest.get("metric_data") or {}
        if isinstance(metric_data, str):
            try:
                metric_data = json.loads(metric_data)
            except json.JSONDecodeError:
                return 0

        return int(metric_data.get("last_post_id", 0) or 0)
