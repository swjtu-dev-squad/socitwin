from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, Iterator, List, Optional

from app.memory.config import MemoryMode
from app.models.agent_monitor import (
    AgentActionSummary,
    AgentDetailProfile,
    AgentDetailResponse,
    AgentDetailStatus,
    AgentGraphEdge,
    AgentGraphNode,
    AgentMemoryRetrieval,
    AgentMemoryRetrievalItem,
    AgentMemorySnapshot,
    AgentMonitorGraph,
    AgentMonitorResponse,
    AgentMonitorSimulation,
    AgentOverview,
    AgentSeenPost,
    AgentTimelineItem,
)
from app.models.simulation import Agent, MemoryDebugAgentStatus, MemoryDebugStatus
from app.memory.retrieval_policy import RetrievalPolicy
from app.services.simulation_service import SimulationService


logger = logging.getLogger(__name__)


class AgentMonitorService:
    """Aggregate simulation, SQLite, and memory debug data for the /agents page."""

    def __init__(self, simulation_service: SimulationService):
        self.simulation_service = simulation_service
        self.retrieval_policy = RetrievalPolicy()

    async def get_monitor(self) -> AgentMonitorResponse:
        status = await self.simulation_service.get_status()
        memory_debug = await self._get_memory_debug_status()

        stats_by_agent: dict[int, _AgentStats] = {}
        edges: list[AgentGraphEdge] = []
        with self._connect_db() as conn:
            if conn is not None:
                stats_by_agent = self._collect_agent_stats(conn)
                edges = self._collect_graph_edges(conn)

        memory_by_agent = {
            agent.agent_id: agent for agent in memory_debug.agents
        } if memory_debug is not None else {}

        agents = [
            self._build_overview(
                agent,
                stats_by_agent.get(agent.id, _AgentStats()),
                memory_by_agent.get(agent.id),
                memory_debug,
            )
            for agent in status.agents
        ]
        agents.sort(
            key=lambda item: (-float(item.influence or 0), -float(item.activity or 0), item.id)
        )

        nodes = [
            AgentGraphNode(
                id=agent.id,
                name=agent.name,
                role=agent.role,
                roleLabel=agent.roleLabel,
                influence=agent.influence,
                activity=agent.activity,
                status=agent.status,
                country=agent.country,
                city=agent.city,
                followerCount=agent.followerCount,
                followingCount=agent.followingCount,
                interactionCount=agent.interactionCount,
            )
            for agent in agents
        ]

        metrics = status.metrics_summary
        propagation = getattr(metrics, "propagation", None) if metrics else None
        herd_effect = getattr(metrics, "herd_effect", None) if metrics else None

        return AgentMonitorResponse(
            simulation=AgentMonitorSimulation(
                running=status.state.value == "running",
                paused=status.state.value == "paused",
                currentStep=status.current_step,
                currentRound=status.current_step // 10 if status.current_step else None,
                platform=status.platform.value,
                recsys=getattr(self.simulation_service.oasis_manager, "_config", None).recsys_type
                if getattr(self.simulation_service.oasis_manager, "_config", None)
                else None,
                topic=None,
                polarization=status.polarization,
                propagationScale=getattr(propagation, "scale", None),
                propagationDepth=getattr(propagation, "depth", None),
                propagationBreadth=getattr(propagation, "max_breadth", None),
                herdIndex=getattr(herd_effect, "conformity_index", None),
                memoryMode=status.memory_mode.value,
            ),
            graph=AgentMonitorGraph(nodes=nodes, edges=edges),
            agents=agents,
            updatedAt=(status.updated_at or datetime.now()).isoformat(),
        )

    async def get_detail(self, agent_id: int) -> AgentDetailResponse:
        status = await self.simulation_service.get_status()
        agent = next((item for item in status.agents if item.id == agent_id), None)
        if agent is None:
            raise KeyError(f"Agent {agent_id} not found")

        memory_debug = await self._get_memory_debug_status()
        memory_agent = None
        if memory_debug is not None:
            memory_agent = next(
                (item for item in memory_debug.agents if item.agent_id == agent_id),
                None,
            )

        stats = _AgentStats()
        timeline: list[AgentTimelineItem] = []
        seen_posts: list[AgentSeenPost] = []
        with self._connect_db() as conn:
            if conn is not None:
                stats_by_agent = self._collect_agent_stats(conn)
                stats = stats_by_agent.get(agent_id, _AgentStats())
                timeline = self._collect_timeline(conn, agent_id, limit=10)
                seen_posts = self._collect_seen_posts(conn, agent_id, limit=10)

        role = self._derive_role(agent.description)
        role_label = self._derive_role_label(role, agent.description)
        profile = getattr(agent, "profile", None) or {}
        tags = list(agent.interests or [])
        if not tags:
            tags = _clean_list(profile.get("interests", []))

        memory = self._build_memory_snapshot(memory_agent, memory_debug)
        last_action = (
            AgentActionSummary(
                type=timeline[0].type,
                content=timeline[0].content,
                reason=timeline[0].reason or "",
                timestamp=timeline[0].timestamp,
            )
            if timeline
            else None
        )

        return AgentDetailResponse(
            profile=AgentDetailProfile(
                id=str(agent.id),
                name=agent.name,
                user_name=agent.user_name,
                bio=agent.bio or agent.description or "",
                personaKey=role,
                personaDescription=agent.description or "",
                roleLabel=role_label,
                gender=profile.get("gender"),
                age=_safe_int(profile.get("age")),
                mbti=profile.get("mbti"),
                country=profile.get("country"),
                city=profile.get("city"),
                occupation=profile.get("occupation"),
                tags=tags,
            ),
            status=AgentDetailStatus(
                state=stats.status,
                influence=float(agent.influence or 0.0),
                activity=float(agent.activity or 0.0),
                followerCount=stats.follower_count,
                followingCount=stats.following_count or len(agent.following),
                interactionCount=stats.interaction_count,
                polarization=agent.polarization,
                contextTokens=memory.debug.get("lastPromptTokens"),
                retrievedMemories=memory.debug.get("lastInjectedCount"),
                seenAgentsCount=None,
            ),
            currentViewpoint=self._build_current_viewpoint(agent, timeline),
            lastAction=last_action,
            recentTimeline=timeline,
            seenPosts=seen_posts,
            memory=memory,
        )

    async def _get_memory_debug_status(self) -> Optional[MemoryDebugStatus]:
        try:
            return await self.simulation_service.get_memory_debug_status()
        except Exception as exc:
            logger.debug("Memory debug status unavailable for monitor: %s", exc)
            return None

    @contextmanager
    def _connect_db(self) -> Iterator[Optional[sqlite3.Connection]]:
        db_path = self.simulation_service.oasis_manager._db_path
        if not db_path or not os.path.exists(db_path):
            yield None
            return

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _collect_agent_stats(self, conn: sqlite3.Connection) -> dict[int, "_AgentStats"]:
        stats: dict[int, _AgentStats] = {}
        agent_ids = self._query_values(conn, "user", "user_id")

        for agent_id_value in agent_ids:
            agent_id = _safe_int(agent_id_value)
            if agent_id is None:
                continue

            followees = [
                str(item)
                for item in self._query_rows(
                    conn,
                    "SELECT followee_id FROM follow WHERE follower_id = ?",
                    (agent_id,),
                    required_tables=("follow",),
                )
            ]
            follower_count = self._query_count(
                conn,
                "SELECT COUNT(*) FROM follow WHERE followee_id = ?",
                (agent_id,),
                required_tables=("follow",),
            )
            post_count = self._query_count(
                conn,
                "SELECT COUNT(*) FROM post WHERE user_id = ?",
                (agent_id,),
                required_tables=("post",),
            )
            comment_count = self._query_count(
                conn,
                "SELECT COUNT(*) FROM comment WHERE user_id = ?",
                (agent_id,),
                required_tables=("comment",),
            )
            like_count = self._query_count(
                conn,
                'SELECT COUNT(*) FROM "like" WHERE user_id = ?',
                (agent_id,),
                required_tables=("like",),
            )
            dislike_count = self._query_count(
                conn,
                "SELECT COUNT(*) FROM dislike WHERE user_id = ?",
                (agent_id,),
                required_tables=("dislike",),
            )
            action_count = self._query_count(
                conn,
                "SELECT COUNT(*) FROM trace WHERE user_id = ?",
                (agent_id,),
                required_tables=("trace",),
            )
            latest_rows = self._query_dicts(
                conn,
                """
                SELECT action, info, created_at
                FROM trace
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (agent_id,),
                required_tables=("trace",),
            )
            latest_action = (
                self._build_action_summary(latest_rows[0])
                if latest_rows
                else None
            )
            status = self._derive_status(action_count, latest_action)

            stats[agent_id] = _AgentStats(
                followees=followees,
                follower_count=follower_count,
                following_count=len(followees),
                interaction_count=(
                    post_count
                    + comment_count
                    + like_count
                    + dislike_count
                    + follower_count
                    + len(followees)
                ),
                latest_action=latest_action,
                status=status,
            )

        return stats

    def _collect_graph_edges(self, conn: sqlite3.Connection) -> list[AgentGraphEdge]:
        edges: list[AgentGraphEdge] = []

        for row in self._query_dicts(
            conn,
            "SELECT follower_id, followee_id FROM follow",
            required_tables=("follow",),
        ):
            edges.append(
                AgentGraphEdge(
                    source=str(row.get("follower_id")),
                    target=str(row.get("followee_id")),
                    type="follow",
                    weight=1,
                    active=True,
                )
            )

        posts_by_id = {
            row.get("post_id"): row.get("user_id")
            for row in self._query_dicts(
                conn,
                "SELECT post_id, user_id FROM post",
                required_tables=("post",),
            )
        }

        for row in self._query_dicts(
            conn,
            'SELECT post_id, user_id FROM "like"',
            required_tables=("like", "post"),
        ):
            target = posts_by_id.get(row.get("post_id"))
            if target is None or target == row.get("user_id"):
                continue
            edges.append(
                AgentGraphEdge(
                    source=str(row.get("user_id")),
                    target=str(target),
                    type="interaction",
                    actionType="LIKE_POST",
                    weight=1,
                    active=True,
                )
            )

        for row in self._query_dicts(
            conn,
            "SELECT post_id, user_id FROM comment",
            required_tables=("comment", "post"),
        ):
            target = posts_by_id.get(row.get("post_id"))
            if target is None or target == row.get("user_id"):
                continue
            edges.append(
                AgentGraphEdge(
                    source=str(row.get("user_id")),
                    target=str(target),
                    type="interaction",
                    actionType="CREATE_COMMENT",
                    weight=1,
                    active=True,
                )
            )

        return edges

    def _collect_timeline(
        self, conn: sqlite3.Connection, agent_id: int, *, limit: int
    ) -> list[AgentTimelineItem]:
        rows = self._query_dicts(
            conn,
            """
            SELECT action, info, created_at
            FROM trace
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (agent_id, limit),
            required_tables=("trace",),
        )
        return [
            AgentTimelineItem(
                timestamp=str(row.get("created_at") or ""),
                type=self._display_action_type(str(row.get("action") or "")),
                content=self._format_action_content(row),
                reason=self._display_action_reason(str(row.get("action") or "")),
            )
            for row in rows
        ]

    def _collect_seen_posts(
        self, conn: sqlite3.Connection, agent_id: int, *, limit: int
    ) -> list[AgentSeenPost]:
        rows = self._query_dicts(
            conn,
            """
            SELECT
                r.post_id,
                p.content,
                p.created_at,
                p.num_likes,
                u.user_name
            FROM rec r
            LEFT JOIN post p ON p.post_id = r.post_id
            LEFT JOIN user u ON u.user_id = p.user_id
            WHERE r.user_id = ?
            ORDER BY r.post_id DESC
            LIMIT ?
            """,
            (agent_id, limit),
            required_tables=("rec", "post", "user"),
        )
        if not rows:
            rows = self._query_dicts(
                conn,
                """
                SELECT
                    p.post_id,
                    p.content,
                    p.created_at,
                    p.num_likes,
                    u.user_name
                FROM post p
                LEFT JOIN user u ON u.user_id = p.user_id
                WHERE p.user_id = ?
                ORDER BY p.created_at DESC
                LIMIT ?
                """,
                (agent_id, limit),
                required_tables=("post", "user"),
            )

        return [
            AgentSeenPost(
                postId=str(row.get("post_id") or ""),
                author=str(row.get("user_name") or ""),
                content=str(row.get("content") or ""),
                timestamp=str(row.get("created_at") or ""),
                numLikes=_safe_int(row.get("num_likes")) or 0,
            )
            for row in rows
        ]

    def _build_overview(
        self,
        agent: Agent,
        stats: "_AgentStats",
        memory_agent: Optional[MemoryDebugAgentStatus],
        memory_debug: Optional[MemoryDebugStatus],
    ) -> AgentOverview:
        role = self._derive_role(agent.description)
        role_label = self._derive_role_label(role, agent.description)
        tags = list(agent.interests or [])
        last_action = stats.latest_action
        following = stats.followees or [str(item) for item in agent.following]

        return AgentOverview(
            id=str(agent.id),
            name=agent.name,
            role=role,
            roleLabel=role_label,
            bio=agent.bio or agent.description or "",
            status=stats.status,
            influence=float(agent.influence or 0.0),
            activity=float(agent.activity or 0.0),
            lastAction=last_action,
            actionContent=last_action.content if last_action else None,
            tags=tags,
            following=following,
            followerCount=stats.follower_count,
            followingCount=stats.following_count or len(following),
            interactionCount=stats.interaction_count,
            memory=self._build_memory_snapshot(memory_agent, memory_debug),
        )

    def _build_memory_snapshot(
        self,
        memory_agent: Optional[MemoryDebugAgentStatus],
        memory_debug: Optional[MemoryDebugStatus],
    ) -> AgentMemorySnapshot:
        if memory_agent is None or memory_debug is None:
            return AgentMemorySnapshot()

        enabled = bool(
            memory_debug.memory_mode == MemoryMode.ACTION_V1
            and memory_debug.longterm_enabled
            and memory_agent.memory_supported
        )

        if not enabled:
            status = "not_configured"
            content = "当前模式未启用 action_v1 长期记忆。"
        elif memory_agent.last_runtime_failure_category:
            status = "error"
            content = (
                f"长期记忆运行异常：{memory_agent.last_runtime_failure_category}"
                f" / {memory_agent.last_runtime_failure_stage or '-'}"
            )
        elif memory_agent.last_recalled_count > 0 or memory_agent.last_injected_count > 0:
            status = "ready"
            content = self._format_recall_content(memory_agent)
        elif memory_agent.last_recall_gate is True:
            status = "empty"
            content = "本轮触发长期记忆检索，但没有可注入的召回结果。"
        else:
            status = "not_configured"
            content = "尚未触发长期记忆召回。"

        items = self._build_retrieval_items(memory_agent)
        debug = {
            "memoryMode": memory_debug.memory_mode.value,
            "memorySupported": memory_agent.memory_supported,
            "recentRetainedStepCount": memory_agent.recent_retained_step_count,
            "recentRetainedStepIds": memory_agent.recent_retained_step_ids,
            "compressedActionBlockCount": memory_agent.compressed_action_block_count,
            "compressedHeartbeatCount": memory_agent.compressed_heartbeat_count,
            "compressedRetainedStepCount": memory_agent.compressed_retained_step_count,
            "totalRetainedStepCount": memory_agent.total_retained_step_count,
            "lastObservationStage": memory_agent.last_observation_stage,
            "lastObservationPromptTokens": memory_agent.last_observation_prompt_tokens,
            "lastPromptTokens": memory_agent.last_prompt_tokens,
            "lastRecallGate": memory_agent.last_recall_gate,
            "lastRecallQuerySource": memory_agent.last_recall_query_source,
            "lastRecallQueryText": memory_agent.last_recall_query_text,
            "lastRecallReasonTrace": memory_agent.last_recall_reason_trace,
            "lastRecalledCount": memory_agent.last_recalled_count,
            "lastInjectedCount": memory_agent.last_injected_count,
            "lastRecalledStepIds": memory_agent.last_recalled_step_ids,
            "lastInjectedStepIds": memory_agent.last_injected_step_ids,
            "lastRuntimeFailureCategory": memory_agent.last_runtime_failure_category,
            "lastRuntimeFailureStage": memory_agent.last_runtime_failure_stage,
            "lastPromptBudgetStatus": memory_agent.last_prompt_budget_status,
            "lastSelectedRecentStepIds": memory_agent.last_selected_recent_step_ids,
            "lastSelectedCompressedKeys": memory_agent.last_selected_compressed_keys,
            "lastSelectedRecallStepIds": memory_agent.last_selected_recall_step_ids,
        }

        return AgentMemorySnapshot(
            length=int(memory_agent.last_prompt_tokens or 0),
            content=content if status == "ready" else "",
            contentSource="retrieval" if status == "ready" else "system_prompt",
            retrieval=AgentMemoryRetrieval(
                length=0,
                enabled=enabled,
                status=status,
                content=content,
                items=items,
            ),
            debug=debug,
        )

    def _build_retrieval_items(
        self, memory_agent: MemoryDebugAgentStatus
    ) -> list[AgentMemoryRetrievalItem]:
        selected_items = [
            item
            for item in (memory_agent.last_selected_recall_items or [])
            if isinstance(item, dict)
        ]
        candidate_items = [
            item
            for item in (memory_agent.last_recall_candidate_items or [])
            if isinstance(item, dict)
        ]

        selected_keys = {
            (item.get("step_id"), item.get("action_index"))
            for item in selected_items
        }
        merged_items = list(candidate_items)
        candidate_keys = {
            (item.get("step_id"), item.get("action_index"))
            for item in candidate_items
        }
        for item in selected_items:
            key = (item.get("step_id"), item.get("action_index"))
            if key not in candidate_keys:
                merged_items.append(item)

        if not merged_items:
            return []

        items: list[AgentMemoryRetrievalItem] = []
        for index, item in enumerate(merged_items):
            step_id = item.get("step_id")
            action_index = item.get("action_index")
            source = (
                "injected"
                if (step_id, action_index) in selected_keys
                else "recalled"
            )
            item_id = f"{source}_step_{step_id}_{action_index if action_index is not None else index}"
            items.append(
                AgentMemoryRetrievalItem(
                    id=item_id,
                    content=self._format_recall_item_content(item),
                    source=source,
                    createdAt=str(step_id) if step_id is not None else None,
                )
            )
        return items

    def _format_recall_content(self, memory_agent: MemoryDebugAgentStatus) -> str:
        lines = ["Long-term memory recall:"]
        if memory_agent.last_recall_query_text:
            lines.append(f"- query: {memory_agent.last_recall_query_text}")
        lines.append(f"- recalled: {memory_agent.last_recalled_count}")
        lines.append(f"- injected: {memory_agent.last_injected_count}")
        if memory_agent.last_injected_step_ids:
            lines.append(
                "- injected steps: "
                + ", ".join(str(item) for item in memory_agent.last_injected_step_ids)
            )
        elif memory_agent.last_recalled_step_ids:
            lines.append(
                "- recalled steps: "
                + ", ".join(str(item) for item in memory_agent.last_recalled_step_ids)
            )
        if memory_agent.last_recall_reason_trace:
            lines.append(
                f"- representative memory: {memory_agent.last_recall_reason_trace}"
            )
        if memory_agent.last_recalled_count > 0 and memory_agent.last_injected_count == 0:
            lines.append("- note: recalled candidates were not injected into the final prompt")
        return "\n".join(lines)

    def _format_recall_item_content(self, item: dict[str, Any]) -> str:
        rendered = self.retrieval_policy.format_results([item], title="").strip()
        if rendered:
            return rendered
        step_id = item.get("step_id", "?")
        return f"long-term memory episode from step {step_id}"

    def _build_action_summary(self, row: dict[str, Any]) -> AgentActionSummary:
        action = str(row.get("action") or "")
        return AgentActionSummary(
            type=self._display_action_type(action),
            content=self._format_action_content(row),
            reason=self._display_action_reason(action),
            timestamp=str(row.get("created_at") or ""),
        )

    def _format_action_content(self, row: dict[str, Any]) -> str:
        action = _normalize_action(str(row.get("action") or ""))
        info = _parse_info(row.get("info"))
        content = _first_text(info, ("content", "text", "message", "query", "body"))

        if action == "refresh":
            return "观察到新的推荐帖"
        if action == "search_posts":
            return f"搜索帖子：{content}" if content else "搜索帖子"
        if action == "search_user":
            return f"搜索用户：{content}" if content else "搜索用户"
        if action == "trend":
            return "查看趋势内容"
        if action in {"create_post", "create_comment", "quote_post", "send_to_group"}:
            return content or self._display_action_reason(action)
        if action in {"like_post", "dislike_post", "repost"}:
            post_id = _first_text(
                info, ("post_id", "postId", "target_post_id", "targetPostId")
            )
            verb = {
                "like_post": "点赞了帖子",
                "dislike_post": "点踩了帖子",
                "repost": "转发了帖子",
            }[action]
            return f"{verb} #{post_id}" if post_id else verb
        if action in {"like_comment", "dislike_comment"}:
            comment_id = _first_text(
                info,
                ("comment_id", "commentId", "target_comment_id", "targetCommentId"),
            )
            verb = "点赞了评论" if action == "like_comment" else "点踩了评论"
            return f"{verb} #{comment_id}" if comment_id else verb
        if action in {"follow", "unfollow", "mute"}:
            target = _first_text(
                info,
                (
                    "target_agent_id",
                    "targetAgentId",
                    "followee_id",
                    "followeeId",
                    "user_id",
                    "userId",
                    "target",
                ),
            )
            verb = {"follow": "关注了", "unfollow": "取消关注了", "mute": "屏蔽了"}[action]
            return f"{verb} Agent {target}" if target else f"{verb}目标智能体"
        if action == "sign_up":
            return "加入了当前模拟"
        if content:
            return content
        return f"执行了 {self._display_action_type(action)}"

    def _display_action_type(self, action: str) -> str:
        normalized = _normalize_action(action)
        return normalized.upper() if normalized else "UNKNOWN"

    def _display_action_reason(self, action: str) -> str:
        normalized = _normalize_action(action)
        labels = {
            "refresh": "刷新信息流",
            "search_posts": "搜索帖子",
            "search_user": "搜索用户",
            "trend": "查看趋势内容",
            "create_post": "发布帖子",
            "create_comment": "发表评论",
            "quote_post": "引用帖子",
            "send_to_group": "发送群组消息",
            "like_post": "点赞帖子",
            "dislike_post": "点踩帖子",
            "like_comment": "点赞评论",
            "dislike_comment": "点踩评论",
            "follow": "关注用户",
            "unfollow": "取消关注",
            "mute": "屏蔽用户",
            "repost": "转发帖子",
            "sign_up": "注册加入",
        }
        return labels.get(normalized, normalized.upper() if normalized else "未知动作")

    def _derive_status(
        self, action_count: int, latest_action: Optional[AgentActionSummary]
    ) -> str:
        if action_count <= 0:
            return "idle"
        if latest_action and latest_action.type in {
            "CREATE_POST",
            "CREATE_COMMENT",
            "QUOTE_POST",
            "SEND_TO_GROUP",
        }:
            return "active"
        return "thinking"

    def _derive_role(self, description: str) -> str:
        text = (description or "").lower()
        if "kol" in text or "influencer" in text or "key opinion leader" in text:
            return "KOL"
        if "skeptic" in text or "critic" in text or "doubter" in text:
            return "Skeptic"
        if "optimistic" in text or "supporter" in text or "enthusiast" in text:
            return "Evangelist"
        if "neutral" in text or "observer" in text or "moderate" in text:
            return "Observer"
        return "Neutral"

    def _derive_role_label(self, role: str, description: str) -> str:
        labels = {
            "KOL": "KOL",
            "Skeptic": "怀疑派",
            "Evangelist": "乐观派",
            "Observer": "中立观察者",
            "Neutral": "中立观察者",
        }
        return labels.get(role) or (description or "中立观察者")[:30]

    def _build_current_viewpoint(
        self, agent: Agent, timeline: list[AgentTimelineItem]
    ) -> Optional[str]:
        for item in timeline:
            if item.type in {"CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"} and item.content:
                return item.content[:160]
        return (agent.bio or agent.description or "")[:160] or None

    def _query_values(
        self, conn: sqlite3.Connection, table: str, column: str
    ) -> list[Any]:
        if not _table_exists(conn, table):
            return []
        try:
            return [row[0] for row in conn.execute(f"SELECT {column} FROM {table}").fetchall()]
        except sqlite3.Error:
            return []

    def _query_count(
        self,
        conn: sqlite3.Connection,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        required_tables: Iterable[str] = (),
    ) -> int:
        if not all(_table_exists(conn, table) for table in required_tables):
            return 0
        try:
            return int(conn.execute(query, params).fetchone()[0] or 0)
        except sqlite3.Error:
            return 0

    def _query_rows(
        self,
        conn: sqlite3.Connection,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        required_tables: Iterable[str] = (),
    ) -> list[Any]:
        if not all(_table_exists(conn, table) for table in required_tables):
            return []
        try:
            return [row[0] for row in conn.execute(query, params).fetchall()]
        except sqlite3.Error:
            return []

    def _query_dicts(
        self,
        conn: sqlite3.Connection,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        required_tables: Iterable[str] = (),
    ) -> list[dict[str, Any]]:
        if not all(_table_exists(conn, table) for table in required_tables):
            return []
        try:
            return [dict(row) for row in conn.execute(query, params).fetchall()]
        except sqlite3.Error as exc:
            logger.debug("Monitor SQLite query skipped: %s", exc)
            return []


class _AgentStats:
    def __init__(
        self,
        *,
        followees: Optional[list[str]] = None,
        follower_count: int = 0,
        following_count: int = 0,
        interaction_count: int = 0,
        latest_action: Optional[AgentActionSummary] = None,
        status: str = "idle",
    ):
        self.followees = followees or []
        self.follower_count = follower_count
        self.following_count = following_count
        self.interaction_count = interaction_count
        self.latest_action = latest_action
        self.status = status


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _parse_info(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except json.JSONDecodeError:
        return {"raw": value}


def _normalize_action(action: str) -> str:
    return str(action or "").strip().lower()


def _first_text(info: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = info.get(key)
        text = _extract_text(value)
        if text:
            return text
    return _extract_text(info.get("raw"))


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _first_text(
            value,
            ("content", "text", "message", "query", "body", "user_name", "user_id"),
        )
    return str(value).strip()
