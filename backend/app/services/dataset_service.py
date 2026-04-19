"""
Dataset Service - SQLite-backed topic and persona seed data access

Provides read-only access to the unified dataset database populated by
fetch_twitter_data.py and exposes clean domain objects for APIs.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from app.models.simulation import AgentConfig, PlatformType
from app.models.topics import (
    TopicContentItem,
    TopicDetail,
    TopicInitialPost,
    TopicListItem,
    TopicProfileItem,
    TopicSettings,
)

logger = logging.getLogger(__name__)


class DatasetServiceError(Exception):
    """Dataset service error."""


class DatasetService:
    """Read-only service for `oasis_datasets.db`."""

    def __init__(self, db_path: str | Path | None = None):
        default_db_path = Path(__file__).resolve().parents[2] / "data" / "datasets" / "oasis_datasets.db"
        self.db_path = Path(db_path or default_db_path).expanduser().resolve()
        logger.info("Dataset Service initialized with db: %s", self.db_path)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self.db_path.exists():
            raise DatasetServiceError(f"Dataset database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only = TRUE")
            yield conn
        except sqlite3.Error as exc:
            raise DatasetServiceError(f"Database query failed: {exc}") from exc
        finally:
            conn.close()

    def _platform_value(self, platform: PlatformType | str) -> str:
        if isinstance(platform, PlatformType):
            return platform.value
        return str(platform).lower()

    def _topic_id_from_row(self, row: sqlite3.Row) -> str:
        return row["news_external_id"] or row["topic_key"]

    def _topic_description(self, row: sqlite3.Row) -> str:
        parts: List[str] = []
        if row["trend_rank"] is not None:
            parts.append(f"#{row['trend_rank']}")
        parts.append(f"{row['post_count']}条主帖")
        parts.append(f"{row['reply_count']}条回复")
        parts.append(f"{row['user_count']}位参与者")
        return " · ".join(parts)

    def _get_topic_row(
        self,
        conn: sqlite3.Connection,
        topic_id: str,
        platform: PlatformType | str,
    ) -> Optional[sqlite3.Row]:
        platform_value = self._platform_value(platform)
        return conn.execute(
            """
            SELECT
                platform,
                topic_key,
                topic_label,
                topic_type,
                trend_rank,
                post_count,
                reply_count,
                user_count,
                first_seen_at,
                last_seen_at,
                news_external_id,
                raw_json,
                type
            FROM topics
            WHERE platform = ?
              AND (news_external_id = ? OR topic_key = ?)
            ORDER BY CASE WHEN news_external_id = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (platform_value, topic_id, topic_id, topic_id),
        ).fetchone()

    def _get_seed_content_row(
        self,
        conn: sqlite3.Connection,
        platform: PlatformType | str,
        topic_key: str,
    ) -> Optional[sqlite3.Row]:
        platform_value = self._platform_value(platform)
        return conn.execute(
            """
            SELECT
                c.external_content_id,
                c.content_type,
                c.author_external_user_id,
                c.parent_external_content_id,
                c.root_external_content_id,
                c.text,
                c.language,
                c.created_at,
                COALESCE(c.like_count, 0) AS like_count,
                COALESCE(c.reply_count, 0) AS reply_count,
                COALESCE(c.share_count, 0) AS share_count,
                COALESCE(c.view_count, 0) AS view_count,
                COALESCE(ct.relevance_score, 1.0) AS relevance_score,
                u.username AS author_username,
                u.display_name AS author_display_name
            FROM content_topics ct
            JOIN contents c
              ON c.platform = ct.platform
             AND c.external_content_id = ct.external_content_id
            LEFT JOIN users u
              ON u.platform = c.platform
             AND u.external_user_id = c.author_external_user_id
            WHERE ct.platform = ?
              AND ct.topic_key = ?
            ORDER BY
                CASE WHEN c.parent_external_content_id IS NULL THEN 0 ELSE 1 END,
                COALESCE(c.reply_count, 0) DESC,
                COALESCE(c.like_count, 0) DESC,
                COALESCE(c.share_count, 0) DESC,
                COALESCE(c.view_count, 0) DESC,
                c.created_at DESC
            LIMIT 1
            """,
            (platform_value, topic_key),
        ).fetchone()

    def _build_topic_detail(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> TopicDetail:
        seed_content_row = self._get_seed_content_row(conn, row["platform"], row["topic_key"])
        seed_content = (
            seed_content_row["text"]
            if seed_content_row and seed_content_row["text"]
            else row["topic_label"]
        )

        return TopicDetail(
            id=self._topic_id_from_row(row),
            name=row["topic_label"],
            description=self._topic_description(row),
            platform=row["platform"],
            topic_key=row["topic_key"],
            topic_type=row["topic_type"],
            trend_rank=row["trend_rank"],
            post_count=row["post_count"],
            reply_count=row["reply_count"],
            user_count=row["user_count"],
            news_external_id=row["news_external_id"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            initial_post=TopicInitialPost(content=seed_content, agent_id=0),
            settings=TopicSettings(trigger_refresh=True),
            available=True,
        )

    def list_topics(
        self,
        platform: PlatformType | str = PlatformType.TWITTER,
        limit: int = 50,
    ) -> List[TopicListItem]:
        platform_value = self._platform_value(platform)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    platform,
                    topic_key,
                    topic_label,
                    topic_type,
                    trend_rank,
                    post_count,
                    reply_count,
                    user_count,
                    first_seen_at,
                    last_seen_at,
                    news_external_id,
                    raw_json,
                    type
                FROM topics
                WHERE platform = ?
                ORDER BY
                    CASE WHEN trend_rank IS NULL THEN 1 ELSE 0 END,
                    trend_rank ASC,
                    last_seen_at DESC,
                    topic_label ASC
                LIMIT ?
                """,
                (platform_value, limit),
            ).fetchall()

        return [
            TopicListItem(
                id=self._topic_id_from_row(row),
                name=row["topic_label"],
                description=self._topic_description(row),
                platform=row["platform"],
                topic_key=row["topic_key"],
                topic_type=row["topic_type"],
                trend_rank=row["trend_rank"],
                post_count=row["post_count"],
                reply_count=row["reply_count"],
                user_count=row["user_count"],
                news_external_id=row["news_external_id"],
                has_initial_post=row["post_count"] > 0,
                settings_trigger_refresh=True,
            )
            for row in rows
        ]

    def get_topic(
        self,
        topic_id: str,
        platform: PlatformType | str = PlatformType.TWITTER,
    ) -> Optional[TopicDetail]:
        with self._connect() as conn:
            row = self._get_topic_row(conn, topic_id, platform)
            if not row:
                return None
            return self._build_topic_detail(conn, row)

    def get_topic_count(self, platform: PlatformType | str = PlatformType.TWITTER) -> int:
        platform_value = self._platform_value(platform)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS topic_count FROM topics WHERE platform = ?",
                (platform_value,),
            ).fetchone()
        return int(row["topic_count"] if row else 0)

    def topic_exists(
        self,
        topic_id: str,
        platform: PlatformType | str = PlatformType.TWITTER,
    ) -> bool:
        return self.get_topic(topic_id, platform) is not None

    def get_topic_profiles(
        self,
        topic_id: str,
        platform: PlatformType | str = PlatformType.TWITTER,
        limit: int = 50,
    ) -> Optional[Tuple[TopicDetail, List[TopicProfileItem]]]:
        with self._connect() as conn:
            topic_row = self._get_topic_row(conn, topic_id, platform)
            if not topic_row:
                return None

            topic = self._build_topic_detail(conn, topic_row)
            rows = conn.execute(
                """
                SELECT
                    ut.external_user_id,
                    ut.role,
                    ut.content_count,
                    u.username,
                    u.display_name,
                    u.bio,
                    u.location,
                    COALESCE(u.verified, 0) AS verified,
                    COALESCE(u.follower_count, 0) AS follower_count,
                    COALESCE(u.following_count, 0) AS following_count,
                    COALESCE(u.tweet_count, 0) AS tweet_count
                FROM user_topics ut
                LEFT JOIN users u
                  ON u.platform = ut.platform
                 AND u.external_user_id = ut.external_user_id
                WHERE ut.platform = ?
                  AND ut.topic_key = ?
                ORDER BY
                    ut.content_count DESC,
                    COALESCE(u.follower_count, 0) DESC,
                    COALESCE(u.verified, 0) DESC,
                    ut.external_user_id ASC
                LIMIT ?
                """,
                (self._platform_value(platform), topic_row["topic_key"], limit),
            ).fetchall()

        max_content_count = max((int(row["content_count"] or 0) for row in rows), default=1)
        profiles: List[TopicProfileItem] = []

        for index, row in enumerate(rows):
            follower_count = int(row["follower_count"] or 0)
            content_count = int(row["content_count"] or 0)
            influence_score = round(min(math.log10(follower_count + 1) / 6, 1.0), 3)
            activity_score = round(content_count / max_content_count, 3)
            username = row["username"] or f"user_{str(row['external_user_id'])[-6:]}"
            display_name = row["display_name"] or username
            role = row["role"] or "participant"
            description = row["bio"] or f"{display_name}围绕话题 {topic.name} 持续参与讨论"
            interests = [topic.name]

            agent_config = AgentConfig(
                agent_id=index,
                user_name=username,
                name=display_name,
                description=description,
                bio=row["bio"],
                profile={
                    "platform": (
                        topic.platform.value
                        if isinstance(topic.platform, PlatformType)
                        else topic.platform
                    ),
                    "topic_key": topic.topic_key,
                    "topic_name": topic.name,
                    "external_user_id": row["external_user_id"],
                    "role": role,
                    "verified": bool(row["verified"]),
                    "follower_count": follower_count,
                    "following_count": int(row["following_count"] or 0),
                    "tweet_count": int(row["tweet_count"] or 0),
                    "location": row["location"],
                    "influence_score": influence_score,
                    "activity_score": activity_score,
                },
                interests=interests,
            )

            profiles.append(
                TopicProfileItem(
                    external_user_id=row["external_user_id"],
                    username=row["username"],
                    display_name=row["display_name"],
                    bio=row["bio"],
                    location=row["location"],
                    verified=bool(row["verified"]),
                    follower_count=follower_count,
                    following_count=int(row["following_count"] or 0),
                    tweet_count=int(row["tweet_count"] or 0),
                    role=role,
                    content_count=content_count,
                    influence_score=influence_score,
                    activity_score=activity_score,
                    interests=interests,
                    agent_config=agent_config,
                )
            )

        return topic, profiles

    def get_topic_contents(
        self,
        topic_id: str,
        platform: PlatformType | str = PlatformType.TWITTER,
        limit: int = 80,
    ) -> Optional[Tuple[TopicDetail, List[TopicContentItem]]]:
        with self._connect() as conn:
            topic_row = self._get_topic_row(conn, topic_id, platform)
            if not topic_row:
                return None

            topic = self._build_topic_detail(conn, topic_row)
            rows = conn.execute(
                """
                SELECT
                    c.external_content_id,
                    c.content_type,
                    c.author_external_user_id,
                    u.username AS author_username,
                    u.display_name AS author_display_name,
                    c.parent_external_content_id,
                    c.root_external_content_id,
                    c.text,
                    c.language,
                    c.created_at,
                    COALESCE(c.like_count, 0) AS like_count,
                    COALESCE(c.reply_count, 0) AS reply_count,
                    COALESCE(c.share_count, 0) AS share_count,
                    COALESCE(c.view_count, 0) AS view_count,
                    COALESCE(ct.relevance_score, 1.0) AS relevance_score
                FROM content_topics ct
                JOIN contents c
                  ON c.platform = ct.platform
                 AND c.external_content_id = ct.external_content_id
                LEFT JOIN users u
                  ON u.platform = c.platform
                 AND u.external_user_id = c.author_external_user_id
                WHERE ct.platform = ?
                  AND ct.topic_key = ?
                ORDER BY
                    CASE WHEN c.parent_external_content_id IS NULL THEN 0 ELSE 1 END,
                    COALESCE(c.reply_count, 0) DESC,
                    COALESCE(c.like_count, 0) DESC,
                    COALESCE(c.share_count, 0) DESC,
                    COALESCE(c.view_count, 0) DESC,
                    c.created_at DESC
                LIMIT ?
                """,
                (self._platform_value(platform), topic_row["topic_key"], limit),
            ).fetchall()

        contents = [
            TopicContentItem(
                external_content_id=row["external_content_id"],
                content_type=row["content_type"],
                author_external_user_id=row["author_external_user_id"],
                author_username=row["author_username"],
                author_display_name=row["author_display_name"],
                parent_external_content_id=row["parent_external_content_id"],
                root_external_content_id=row["root_external_content_id"],
                text=row["text"],
                language=row["language"],
                created_at=row["created_at"],
                like_count=int(row["like_count"] or 0),
                reply_count=int(row["reply_count"] or 0),
                share_count=int(row["share_count"] or 0),
                view_count=int(row["view_count"] or 0),
                relevance_score=float(row["relevance_score"] or 1.0),
            )
            for row in rows
        ]

        return topic, contents
