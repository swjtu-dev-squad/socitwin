"""
Unit tests for oasis_dashboard.longterm
涵盖 EpisodeRecord 和 InMemoryLongTermSidecar 的核心行为。

测试用例列表：
  T1 - EpisodeRecord 基础字段与 token_saving 计算
  T2 - EpisodeRecord.to_dict() 序列化完整性
  T3 - push_episode 单条推送，不触发 compaction
  T4 - push_episode 累计推送触发 compaction，token_saving > 0
  T5 - retrieve 按 last_n 返回正确条数
  T6 - retrieve_summary 返回可读文本
  T7 - compaction 后 _store 长度缩减
  T8 - reset 清空所有状态
  T9 - get_stats 返回正确统计信息
  T10 - 多 Agent 并发推送互不干扰
"""

import asyncio
import pytest
from oasis_dashboard.longterm import EpisodeRecord, InMemoryLongTermSidecar


# ---------------------------------------------------------------------------
# T1 — EpisodeRecord 基础字段与 token_saving
# ---------------------------------------------------------------------------

def test_T1_episode_record_token_saving():
    """未压缩时 token_saving=0；压缩后 token_saving = raw - summary。"""
    ep = EpisodeRecord(step_id=1, agent_id="a1", raw_tokens=500)
    assert ep.token_saving() == 0, "未压缩时 token_saving 应为 0"

    ep.compacted = True
    ep.summary_tokens = 80
    assert ep.token_saving() == 420, "压缩后 token_saving 应为 raw_tokens - summary_tokens"


# ---------------------------------------------------------------------------
# T2 — EpisodeRecord.to_dict() 序列化
# ---------------------------------------------------------------------------

def test_T2_episode_record_to_dict():
    """to_dict() 应包含所有必要字段。"""
    ep = EpisodeRecord(
        step_id=3,
        agent_id="a2",
        raw_tokens=300,
        actions=["CREATE_POST"],
        observations=["post_1"],
    )
    d = ep.to_dict()
    required_keys = {
        "step_id", "agent_id", "raw_tokens", "summary",
        "summary_tokens", "actions", "observations",
        "compacted", "created_at", "token_saving",
    }
    assert required_keys.issubset(d.keys()), f"缺少字段: {required_keys - d.keys()}"
    assert d["step_id"] == 3
    assert d["agent_id"] == "a2"
    assert d["actions"] == ["CREATE_POST"]


# ---------------------------------------------------------------------------
# T3 — 单条推送，不触发 compaction
# ---------------------------------------------------------------------------

def test_T3_push_no_compaction():
    """单条推送时 compacted=False，total_episodes=1。"""
    sidecar = InMemoryLongTermSidecar(compaction_threshold=10)
    ep = EpisodeRecord(step_id=1, agent_id="a1", raw_tokens=100)
    result = asyncio.run(sidecar.push_episode(ep))
    assert result["status"] == "ok"
    assert result["compacted"] is False
    assert result["total_episodes"] == 1


# ---------------------------------------------------------------------------
# T4 — 累计推送触发 compaction
# ---------------------------------------------------------------------------

def test_T4_push_triggers_compaction():
    """推送 compaction_threshold 条后应触发 compaction，token_saving > 0。"""
    sidecar = InMemoryLongTermSidecar(
        compaction_threshold=5,
        compaction_window=3,
        max_summary_tokens=50,
    )
    last_result = None
    for i in range(1, 6):
        ep = EpisodeRecord(
            step_id=i,
            agent_id="a1",
            raw_tokens=200,
            actions=["CREATE_POST"] if i % 2 == 0 else ["LIKE_POST"],
        )
        last_result = asyncio.run(sidecar.push_episode(ep))

    assert last_result["compacted"] is True, "第 5 条推送应触发 compaction"
    assert last_result["token_saving"] > 0, "compaction 后 token_saving 应 > 0"


# ---------------------------------------------------------------------------
# T5 — retrieve 按 last_n 返回正确条数
# ---------------------------------------------------------------------------

def test_T5_retrieve_last_n():
    """retrieve(last_n=3) 应返回最近 3 条记录。"""
    sidecar = InMemoryLongTermSidecar(compaction_threshold=100)
    for i in range(1, 8):
        ep = EpisodeRecord(step_id=i, agent_id="a1", raw_tokens=50)
        asyncio.run(sidecar.push_episode(ep))

    records = asyncio.run(sidecar.retrieve("a1", last_n=3))
    assert len(records) == 3, f"期望 3 条，实际 {len(records)} 条"
    # 最后 3 条的 step_id 应为 5, 6, 7
    step_ids = [r["step_id"] for r in records]
    assert step_ids == [5, 6, 7], f"step_id 顺序错误: {step_ids}"


# ---------------------------------------------------------------------------
# T6 — retrieve_summary 返回可读文本
# ---------------------------------------------------------------------------

def test_T6_retrieve_summary():
    """retrieve_summary 应返回非空字符串，包含 step 信息。"""
    sidecar = InMemoryLongTermSidecar(compaction_threshold=100)
    ep = EpisodeRecord(step_id=1, agent_id="a1", actions=["CREATE_POST"])
    asyncio.run(sidecar.push_episode(ep))

    summary = asyncio.run(sidecar.retrieve_summary("a1"))
    assert isinstance(summary, str) and len(summary) > 0, "摘要不应为空"
    assert "Step 1" in summary, "摘要应包含 step 编号"


# ---------------------------------------------------------------------------
# T7 — compaction 后 _store 长度缩减
# ---------------------------------------------------------------------------

def test_T7_store_length_after_compaction():
    """compaction_window=3，推送 5 条后 _store 应缩减为 5-3+1=3 条。"""
    sidecar = InMemoryLongTermSidecar(
        compaction_threshold=5,
        compaction_window=3,
    )
    for i in range(1, 6):
        ep = EpisodeRecord(step_id=i, agent_id="a1", raw_tokens=100)
        asyncio.run(sidecar.push_episode(ep))

    store_len = len(sidecar._store["a1"])
    assert store_len == 3, f"compaction 后 _store 长度应为 3，实际为 {store_len}"


# ---------------------------------------------------------------------------
# T8 — reset 清空所有状态
# ---------------------------------------------------------------------------

def test_T8_reset():
    """reset 后 _store 为空，统计归零。"""
    sidecar = InMemoryLongTermSidecar(compaction_threshold=5, compaction_window=3)
    for i in range(1, 6):
        ep = EpisodeRecord(step_id=i, agent_id="a1", raw_tokens=100)
        asyncio.run(sidecar.push_episode(ep))

    asyncio.run(sidecar.reset())
    assert len(sidecar._store) == 0, "reset 后 _store 应为空"
    stats = asyncio.run(sidecar.get_stats())
    assert stats["total_token_saving"] == 0
    assert stats["compaction_count"] == 0


# ---------------------------------------------------------------------------
# T9 — get_stats 返回正确统计信息
# ---------------------------------------------------------------------------

def test_T9_get_stats():
    """get_stats 应正确反映 total_agents、total_episodes、compaction_count。"""
    sidecar = InMemoryLongTermSidecar(compaction_threshold=5, compaction_window=3)
    for agent in ["a1", "a2"]:
        for i in range(1, 4):
            ep = EpisodeRecord(step_id=i, agent_id=agent, raw_tokens=100)
            asyncio.run(sidecar.push_episode(ep))

    stats = asyncio.run(sidecar.get_stats())
    assert stats["total_agents"] == 2
    assert stats["total_episodes"] == 6
    assert stats["compaction_count"] == 0  # 未达阈值


# ---------------------------------------------------------------------------
# T10 — 多 Agent 并发推送互不干扰
# ---------------------------------------------------------------------------

def test_T10_multi_agent_isolation():
    """不同 Agent 的情节应相互隔离，不互相污染。"""
    sidecar = InMemoryLongTermSidecar(compaction_threshold=100)
    for i in range(1, 4):
        asyncio.run(sidecar.push_episode(
            EpisodeRecord(step_id=i, agent_id="agent_A", raw_tokens=50)
        ))
    for i in range(1, 6):
        asyncio.run(sidecar.push_episode(
            EpisodeRecord(step_id=i, agent_id="agent_B", raw_tokens=50)
        ))

    records_a = asyncio.run(sidecar.retrieve("agent_A"))
    records_b = asyncio.run(sidecar.retrieve("agent_B"))

    assert all(r["agent_id"] == "agent_A" for r in records_a), "agent_A 的记录中混入了其他 Agent"
    assert all(r["agent_id"] == "agent_B" for r in records_b), "agent_B 的记录中混入了其他 Agent"
    assert len(records_a) == 3
    assert len(records_b) == 5
