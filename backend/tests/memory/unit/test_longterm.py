from pathlib import Path
from unittest.mock import patch

from app.memory.longterm import (
    ChromaLongtermStore,
    HeuristicTextEmbedding,
    OpenAICompatibleTextEmbedding,
    build_chroma_longterm_store,
    build_longterm_embedding,
    episode_to_payload,
    payload_to_episode,
)


def _episode(step_id: int, agent_id: str = "a1") -> dict:
    return {
        "memory_kind": "action_episode",
        "agent_id": agent_id,
        "step_id": step_id,
        "action_index": 0,
        "timestamp": float(step_id),
        "platform": "reddit",
        "action_name": "follow",
        "action_category": "relationship_change",
        "action_fact": f"follow(user_id={step_id})",
        "target_type": "user",
        "target_id": step_id,
        "target_snapshot": {"summary": f"user:{step_id}", "evidence_quality": "normal"},
        "target_visible_in_prompt": True,
        "target_resolution_status": "visible_in_prompt",
        "execution_status": "success",
        "local_context": {},
        "authored_content": "",
        "state_changes": [f"followed_user:{step_id}"],
        "outcome": "ok",
        "idle_step_gap": 0,
        "topic": "",
        "query_source": "structured_event_query",
        "action_significance": "medium",
        "evidence_quality": "normal",
        "degraded_evidence": False,
        "summary_text": "",
        "metadata": {},
    }


def test_episode_payload_roundtrip_requires_action_episode_shape() -> None:
    payload = episode_to_payload(_episode(3))
    restored = payload_to_episode(payload)

    assert restored["memory_kind"] == "action_episode"
    assert restored["step_id"] == 3
    assert restored["target_snapshot"]["summary"] == "user:3"


def test_episode_payload_rejects_illegal_query_source() -> None:
    invalid = _episode(3)
    invalid["query_source"] = "bad_source"

    try:
        episode_to_payload(invalid)
    except ValueError as exc:
        assert "Unsupported query_source" in str(exc)
    else:
        raise AssertionError("expected ValueError for bad query_source")


def test_heuristic_embedding_is_deterministic() -> None:
    embedding = HeuristicTextEmbedding(output_dim=8)
    first = embedding.embed_list(["follow user 7"])[0]
    second = embedding.embed_list(["follow user 7"])[0]

    assert first == second
    assert len(first) == 8


def test_build_longterm_embedding_supports_openai_compatible() -> None:
    embedding = build_longterm_embedding(
        backend="openai-compatible",
        output_dim=8,
        model="text-embedding-3-small",
    )
    assert isinstance(embedding, OpenAICompatibleTextEmbedding)


def test_build_longterm_embedding_infers_openai_compatible_dim_when_missing() -> None:
    with patch(
        "app.memory.longterm._infer_openai_compatible_embedding_dim",
        return_value=768,
    ):
        embedding = build_longterm_embedding(
            backend="openai-compatible",
            model="nomic-embed-text:latest",
            base_url="http://127.0.0.1:11434/v1",
        )

    assert isinstance(embedding, OpenAICompatibleTextEmbedding)
    assert embedding.get_output_dim() == 768


def test_chroma_longterm_store_roundtrip_and_agent_filter(tmp_path: Path) -> None:
    store = build_chroma_longterm_store(
        collection_name="memory-test",
        output_dim=8,
        embedding_backend="heuristic",
        client_type="persistent",
        path=str(tmp_path),
        delete_collection_on_close=True,
    )

    assert isinstance(store, ChromaLongtermStore)
    store.write_episodes([_episode(7, "agent-a"), _episode(8, "agent-b")])

    results = store.retrieve_relevant("follow user:7", limit=3, agent_id="agent-a")

    assert len(results) == 1
    assert results[0]["agent_id"] == "agent-a"
    assert results[0]["step_id"] == 7

    store.clear()


def test_chroma_longterm_store_accepts_empty_state_changes(tmp_path: Path) -> None:
    store = build_chroma_longterm_store(
        collection_name="memory-empty-state-changes",
        output_dim=8,
        embedding_backend="heuristic",
        client_type="persistent",
        path=str(tmp_path),
        delete_collection_on_close=True,
    )

    episode = _episode(9, "agent-a")
    episode["state_changes"] = []

    store.write_episode(episode)
    results = store.retrieve_relevant("follow user 9", limit=3, agent_id="agent-a")

    assert len(results) == 1
    assert results[0]["step_id"] == 9
    assert results[0]["state_changes"] == []

    store.clear()
