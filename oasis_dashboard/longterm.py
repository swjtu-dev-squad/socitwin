"""
Long-Term Memory Sidecar for OASIS Dashboard
实现 Issue #26 / #27 所要求的 Episodic Compaction 与 Long-Term Sidecar 接口。

本模块提供：
- EpisodeRecord：单条情节记录的数据结构（Step Memory Contract）
- InMemoryLongTermSidecar：基于内存的长期记忆旁路实现（A/B 侧握手接口）

设计原则：
(1) 接口契约优先：所有公开方法均有明确的入参/返回类型，便于后续替换为持久化实现。
(2) 最小依赖：仅依赖 Python 标准库，不引入外部包。
(3) 线程安全：使用 asyncio.Lock 保护并发写入。
(4) 可观测：每次 compaction 记录 token 节省量，供 step() 返回值暴露。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# EpisodeRecord — Step Memory Contract
# ---------------------------------------------------------------------------

@dataclass
class EpisodeRecord:
    """
    单条情节记录（Step Memory Contract）。

    每完成一个 step，引擎应生成一条 EpisodeRecord 并交给 Sidecar 管理。
    字段设计遵循 Issue #26 的接口约定：

    Attributes:
        step_id:        对应的仿真步骤编号（从 1 开始）。
        agent_id:       产生该情节的 Agent 标识符。
        raw_tokens:     本 step 该 Agent 的原始上下文 token 数。
        summary:        LLM 生成的情节摘要文本（compaction 后填入）。
        summary_tokens: 摘要的 token 数（compaction 后填入）。
        actions:        本 step 该 Agent 执行的动作列表（如 CREATE_POST、LIKE 等）。
        observations:   本 step 该 Agent 的观察列表（如看到的帖子 ID 列表）。
        compacted:      是否已经过 Episodic Compaction 压缩。
        created_at:     记录创建的 Unix 时间戳。
    """

    step_id: int
    agent_id: str
    raw_tokens: int = 0
    summary: str = ""
    summary_tokens: int = 0
    actions: List[str] = field(default_factory=list)
    observations: List[Any] = field(default_factory=list)
    compacted: bool = False
    created_at: float = field(default_factory=time.time)

    def token_saving(self) -> int:
        """返回 compaction 节省的 token 数（未压缩时为 0）。"""
        if not self.compacted or self.summary_tokens == 0:
            return 0
        return max(0, self.raw_tokens - self.summary_tokens)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，便于 JSON 传输和日志记录。"""
        return {
            "step_id": self.step_id,
            "agent_id": self.agent_id,
            "raw_tokens": self.raw_tokens,
            "summary": self.summary,
            "summary_tokens": self.summary_tokens,
            "actions": self.actions,
            "observations": self.observations,
            "compacted": self.compacted,
            "created_at": self.created_at,
            "token_saving": self.token_saving(),
        }


# ---------------------------------------------------------------------------
# InMemoryLongTermSidecar — A/B 侧握手接口
# ---------------------------------------------------------------------------

class InMemoryLongTermSidecar:
    """
    基于内存的长期记忆旁路（Long-Term Sidecar）。

    职责：
    - A 侧（主引擎）：通过 push_episode() 将每步情节推送给 Sidecar。
    - B 侧（记忆检索）：通过 retrieve() 按 agent_id 检索历史情节摘要。
    - Compaction：当某 Agent 的情节数超过 compaction_threshold 时，
      自动将最旧的若干条情节合并为一条摘要记录，释放 token 空间。

    当前实现为纯内存版本，适用于单进程仿真。后续可替换为 SQLite 或 Redis 持久化版本。

    Args:
        compaction_threshold:   触发 compaction 的单 Agent 情节数阈值（默认 10）。
        max_summary_tokens:     摘要的最大 token 数估算上限（默认 200）。
        compaction_window:      每次 compaction 合并的情节数（默认 5）。
    """

    def __init__(
        self,
        compaction_threshold: int = 10,
        max_summary_tokens: int = 200,
        compaction_window: int = 5,
    ):
        self.compaction_threshold = compaction_threshold
        self.max_summary_tokens = max_summary_tokens
        self.compaction_window = compaction_window

        # 内部存储：agent_id -> List[EpisodeRecord]
        self._store: Dict[str, List[EpisodeRecord]] = {}
        # 统计：累计节省的 token 数
        self._total_token_saving: int = 0
        # 统计：compaction 执行次数
        self._compaction_count: int = 0
        # 异步锁，保护并发写入
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # A 侧接口：主引擎调用
    # ------------------------------------------------------------------

    async def push_episode(self, record: EpisodeRecord) -> Dict[str, Any]:
        """
        （A 侧）推送一条情节记录。

        若该 Agent 的情节数达到 compaction_threshold，自动触发 compaction。

        Args:
            record: 待推送的 EpisodeRecord 实例。

        Returns:
            {
                "status": "ok",
                "compacted": bool,          # 本次推送是否触发了 compaction
                "token_saving": int,        # 本次 compaction 节省的 token 数（未触发时为 0）
                "total_episodes": int,      # 该 Agent 当前情节总数
            }
        """
        async with self._lock:
            agent_id = record.agent_id
            if agent_id not in self._store:
                self._store[agent_id] = []
            self._store[agent_id].append(record)

            compacted = False
            token_saving = 0

            if len(self._store[agent_id]) >= self.compaction_threshold:
                saving = await self._compact_agent(agent_id)
                compacted = True
                token_saving = saving

            return {
                "status": "ok",
                "compacted": compacted,
                "token_saving": token_saving,
                "total_episodes": len(self._store.get(agent_id, [])),
            }

    # ------------------------------------------------------------------
    # B 侧接口：记忆检索
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        agent_id: str,
        last_n: int = 5,
        include_compacted: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        （B 侧）检索指定 Agent 的最近 N 条情节记录。

        Args:
            agent_id:           目标 Agent 标识符。
            last_n:             返回最近的情节数量（默认 5）。
            include_compacted:  是否包含已压缩的情节（默认 True）。

        Returns:
            情节记录列表（按 step_id 升序），每条为 EpisodeRecord.to_dict() 格式。
        """
        async with self._lock:
            episodes = self._store.get(agent_id, [])
            if not include_compacted:
                episodes = [e for e in episodes if not e.compacted]
            return [e.to_dict() for e in episodes[-last_n:]]

    async def retrieve_summary(self, agent_id: str) -> str:
        """
        （B 侧）返回指定 Agent 的历史情节文本摘要，可直接注入 LLM 上下文。

        Returns:
            多行字符串，每行为一条情节的简要描述。
        """
        async with self._lock:
            episodes = self._store.get(agent_id, [])
            if not episodes:
                return ""
            lines = []
            for ep in episodes:
                if ep.compacted and ep.summary:
                    lines.append(f"[Step {ep.step_id}] (compacted) {ep.summary}")
                else:
                    action_str = ", ".join(ep.actions) if ep.actions else "no action"
                    lines.append(f"[Step {ep.step_id}] actions={action_str}")
            return "\n".join(lines)

    # ------------------------------------------------------------------
    # 状态查询接口
    # ------------------------------------------------------------------

    async def get_stats(self) -> Dict[str, Any]:
        """
        返回 Sidecar 的运行统计信息，供 step() 返回值暴露。

        Returns:
            {
                "total_agents":         int,  # 已追踪的 Agent 数量
                "total_episodes":       int,  # 所有 Agent 的情节总数
                "total_token_saving":   int,  # 累计节省的 token 数
                "compaction_count":     int,  # compaction 执行次数
            }
        """
        async with self._lock:
            total_episodes = sum(len(v) for v in self._store.values())
            return {
                "total_agents": len(self._store),
                "total_episodes": total_episodes,
                "total_token_saving": self._total_token_saving,
                "compaction_count": self._compaction_count,
            }

    # ------------------------------------------------------------------
    # B 侧接口：write_episode / write_episodes（Issue #27 契约）
    # ------------------------------------------------------------------

    async def write_episode(self, record: "EpisodeRecord") -> Dict[str, Any]:
        """
        （B 侧）写入单条情节记录。等同于 push_episode，提供 Issue #27 命名契约。
        """
        return await self.push_episode(record)

    async def write_episodes(self, records: List["EpisodeRecord"]) -> Dict[str, Any]:
        """
        （B 侧）批量写入情节记录。

        Returns:
            {"status": "ok", "written": int, "compacted": int}
        """
        written = 0
        compacted = 0
        for record in records:
            result = await self.push_episode(record)
            written += 1
            if result.get("compacted"):
                compacted += 1
        return {"status": "ok", "written": written, "compacted": compacted}

    # ------------------------------------------------------------------
    # B 侧接口：retrieve_relevant（Issue #27 契约）
    # ------------------------------------------------------------------

    VALID_QUERY_SOURCES = frozenset([
        "distilled topic",
        "recent episodic summary",
        "structured event query",
    ])

    async def retrieve_relevant(
        self,
        agent_id: str,
        query: str,
        query_source: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        （B 侧）按 query_source 类型检索相关情节。

        Args:
            agent_id:     目标 Agent 标识符。
            query:        查询文本。
            query_source: 查询来源类型，必须是以下之一：
                          - "distilled topic"
                          - "recent episodic summary"
                          - "structured event query"
            top_k:        返回最多 top_k 条结果。

        Returns:
            情节记录列表（按相关性排序）。

        Raises:
            ValueError: 当 query_source 不合法时。
        """
        if query_source not in self.VALID_QUERY_SOURCES:
            raise ValueError(
                f"Invalid query_source: '{query_source}'. "
                f"Must be one of: {sorted(self.VALID_QUERY_SOURCES)}"
            )
        async with self._lock:
            episodes = self._store.get(agent_id, [])
            if not episodes:
                return []
            # 简单关键词匹配（后续可替换为 embedding 检索）
            query_lower = query.lower()
            scored = []
            for ep in episodes:
                score = 0.0
                # 匹配 actions
                for action in ep.actions:
                    if query_lower in action.lower():
                        score += 2.0
                # 匹配 summary
                if ep.summary and query_lower in ep.summary.lower():
                    score += 3.0
                # 匹配 observations
                for obs in ep.observations:
                    if isinstance(obs, str) and query_lower in obs.lower():
                        score += 1.0
                # 对于 recent episodic summary，偏好最新的情节
                if query_source == "recent episodic summary":
                    score += ep.step_id * 0.1
                scored.append((score, ep))
            # 按分数降序排序，返回 top_k
            scored.sort(key=lambda x: x[0], reverse=True)
            return [ep.to_dict() for _, ep in scored[:top_k]]

    async def reset(self) -> None:
        """清空所有情节记录，重置统计信息（仿真重置时调用）。"""
        async with self._lock:
            self._store.clear()
            self._total_token_saving = 0
            self._compaction_count = 0

    # ------------------------------------------------------------------
    # 内部 compaction 逻辑
    # ------------------------------------------------------------------

    async def _compact_agent(self, agent_id: str) -> int:
        """
        对指定 Agent 的最旧 compaction_window 条情节执行 compaction。

        当前实现为启发式摘要（拼接 action 列表），后续可替换为 LLM 摘要。

        Returns:
            本次 compaction 节省的 token 数估算值。
        """
        episodes = self._store[agent_id]
        window = episodes[: self.compaction_window]

        # 生成启发式摘要
        action_summary = []
        total_raw = 0
        for ep in window:
            total_raw += ep.raw_tokens
            if ep.actions:
                action_summary.append(f"step{ep.step_id}:[{','.join(ep.actions)}]")

        summary_text = "; ".join(action_summary) if action_summary else "(no actions)"
        # 估算摘要 token 数（按字符数 / 4 粗略估算）
        summary_tokens = min(len(summary_text) // 4 + 1, self.max_summary_tokens)

        # 将 window 中的情节合并为第一条，其余删除
        window[0].summary = summary_text
        window[0].summary_tokens = summary_tokens
        window[0].compacted = True

        # 删除 window[1:] 中的情节
        for ep in window[1:]:
            episodes.remove(ep)

        token_saving = max(0, total_raw - summary_tokens)
        self._total_token_saving += token_saving
        self._compaction_count += 1

        return token_saving
