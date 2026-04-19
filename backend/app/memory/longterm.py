from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Mapping, Protocol, TypedDict

from camel.embeddings.base import BaseEmbedding
from camel.storages import ChromaStorage
from camel.storages.vectordb_storages import (
    VectorDBQuery,
    VectorDBQueryResult,
    VectorRecord,
)


TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
SERIALIZED_PAYLOAD_KEY = "episode_payload_json"
ALLOWED_QUERY_SOURCES = frozenset(
    {
        "distilled_topic",
        "recent_episodic_summary",
        "structured_event_query",
    }
)
REQUIRED_ACTION_EPISODE_KEYS = frozenset(
    {
        "memory_kind",
        "agent_id",
        "step_id",
        "action_index",
        "timestamp",
        "platform",
        "action_name",
        "action_category",
        "target_type",
        "target_snapshot",
        "target_visible_in_prompt",
        "target_resolution_status",
        "execution_status",
        "local_context",
        "authored_content",
        "state_changes",
        "outcome",
        "idle_step_gap",
        "topic",
        "query_source",
        "action_significance",
    }
)
ACTION_SCORING_WEIGHTS = {
    "topic": 4,
    "action_name": 5,
    "action_category": 2,
    "action_fact": 5,
    "target_snapshot": 5,
    "authored_content": 4,
    "local_context": 3,
    "outcome": 2,
    "state_changes": 1,
}


class ActionEpisodeLike(TypedDict, total=False):
    memory_kind: str
    agent_id: str
    step_id: str | int
    action_index: int
    timestamp: float | int
    platform: str
    action_name: str
    action_category: str
    action_fact: str
    target_type: str
    target_id: Any
    target_snapshot: Mapping[str, Any]
    target_visible_in_prompt: bool
    target_resolution_status: str
    execution_status: str
    local_context: Mapping[str, Any]
    authored_content: str
    state_changes: Any
    outcome: Any
    idle_step_gap: int
    topic: str
    query_source: str
    action_significance: str
    evidence_quality: str
    degraded_evidence: bool
    summary_text: str
    metadata: Mapping[str, Any]


class LongtermStore(Protocol):
    def write_episode(self, episode: ActionEpisodeLike) -> None:
        ...

    def write_episodes(self, episodes: list[ActionEpisodeLike]) -> None:
        ...

    def retrieve_relevant(
        self,
        query: str,
        limit: int,
        *,
        agent_id: str | int | None = None,
    ) -> list[ActionEpisodeLike]:
        ...

    def clear(self) -> None:
        ...


class HeuristicTextEmbedding(BaseEmbedding[str]):
    def __init__(self, output_dim: int = 128):
        if output_dim <= 0:
            raise ValueError("output_dim must be positive.")
        self.output_dim = output_dim

    def embed_list(self, objs: list[str], **kwargs: Any) -> list[list[float]]:
        del kwargs
        return [self._embed_text(obj or "") for obj in objs]

    def get_output_dim(self) -> int:
        return self.output_dim

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.output_dim
        tokens = _tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.output_dim
            sign = -1.0 if digest[4] % 2 else 1.0
            magnitude = 1.0 + (digest[5] / 255.0)
            vector[bucket] += sign * magnitude

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class OpenAICompatibleTextEmbedding(BaseEmbedding[str]):
    def __init__(
        self,
        *,
        model: str,
        output_dim: int,
        api_key: str | None = None,
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("embedding model must be non-empty.")
        if output_dim <= 0:
            raise ValueError("output_dim must be positive.")
        self.model = model.strip()
        self.output_dim = output_dim
        self._client = client
        self._api_key = api_key
        self._base_url = base_url

    def embed_list(self, objs: list[str], **kwargs: Any) -> list[list[float]]:
        client = self._client
        if client is None:
            client = self._build_client()
            self._client = client
        response = client.embeddings.create(
            model=self.model,
            input=[obj or "" for obj in objs],
            **kwargs,
        )
        embeddings = [list(item.embedding) for item in response.data]
        for embedding in embeddings:
            if len(embedding) != self.output_dim:
                raise ValueError(
                    "embedding output dimension mismatch: "
                    f"expected {self.output_dim}, got {len(embedding)}"
                )
        return embeddings

    def get_output_dim(self) -> int:
        return self.output_dim

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI-compatible embeddings require the 'openai' package."
            ) from exc

        kwargs: dict[str, Any] = {}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._api_key:
            kwargs["api_key"] = self._api_key
        elif self._base_url:
            kwargs["api_key"] = "EMPTY"
        return OpenAI(**kwargs)


class SidecarChromaStorage(ChromaStorage):
    def add(self, records: list[VectorRecord], **kwargs: Any) -> None:
        serialized_records = [
            VectorRecord(
                vector=record.vector,
                id=record.id,
                payload=_serialize_payload(record.payload),
            )
            for record in records
        ]
        super().add(serialized_records, **kwargs)

    def query(
        self,
        query: VectorDBQuery,
        **kwargs: Any,
    ) -> list[VectorDBQueryResult]:
        results = super().query(query, **kwargs)
        for result in results:
            result.record.payload = _deserialize_payload(result.record.payload)
        return results


class ChromaLongtermStore:
    def __init__(
        self,
        *,
        storage: SidecarChromaStorage,
        embedding: BaseEmbedding[str],
    ) -> None:
        self.storage = storage
        self.embedding = embedding

    def write_episode(self, episode: ActionEpisodeLike) -> None:
        self.write_episodes([episode])

    def write_episodes(self, episodes: list[ActionEpisodeLike]) -> None:
        vector_records = []
        for episode in episodes:
            payload = episode_to_payload(episode)
            vector_records.append(
                VectorRecord(
                    vector=self.embedding.embed_list([_episode_document(payload)])[0],
                    id=_episode_record_id(payload),
                    payload=payload,
                )
            )
        if vector_records:
            self.storage.add(vector_records)

    def retrieve_relevant(
        self,
        query: str,
        limit: int,
        *,
        agent_id: str | int | None = None,
    ) -> list[ActionEpisodeLike]:
        _validate_limit(limit)
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        expanded_limit = max(limit, limit * 3)
        results = self.storage.query(
            VectorDBQuery(
                query_vector=self.embedding.embed_list([normalized_query])[0],
                top_k=expanded_limit,
            ),
            **_agent_query_filter_kwargs(agent_id),
        )
        payloads = [payload_to_episode(result.record.payload or {}) for result in results]
        return _rerank_retrieved_payloads(payloads, query=normalized_query, limit=limit)

    def clear(self) -> None:
        self.storage.clear()


def build_chroma_longterm_store(
    *,
    collection_name: str,
    output_dim: int | None = None,
    embedding_backend: str = "heuristic",
    embedding_model: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
    client_type: str = "persistent",
    path: str | None = None,
    delete_collection_on_close: bool = True,
) -> ChromaLongtermStore:
    embedding = build_longterm_embedding(
        backend=embedding_backend,
        output_dim=output_dim,
        model=embedding_model,
        api_key=embedding_api_key,
        base_url=embedding_base_url,
    )
    storage = SidecarChromaStorage(
        vector_dim=embedding.get_output_dim(),
        collection_name=collection_name,
        client_type=client_type,
        path=path,
        delete_collection_on_del=delete_collection_on_close,
    )
    return ChromaLongtermStore(storage=storage, embedding=embedding)


def build_longterm_embedding(
    *,
    backend: str,
    output_dim: int | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> BaseEmbedding[str]:
    normalized_backend = str(backend or "heuristic").strip().lower()
    if normalized_backend in {"heuristic", "hash", "offline"}:
        return HeuristicTextEmbedding(output_dim=output_dim or 128)
    if normalized_backend in {"openai", "openai_compatible", "openai-compatible"}:
        resolved_output_dim = output_dim
        if resolved_output_dim is None:
            resolved_output_dim = _infer_openai_compatible_embedding_dim(
                model=model or "text-embedding-3-small",
                api_key=api_key,
                base_url=base_url,
            )
        return OpenAICompatibleTextEmbedding(
            model=model or "text-embedding-3-small",
            output_dim=resolved_output_dim,
            api_key=api_key,
            base_url=base_url,
        )
    raise ValueError(f"Unsupported long-term embedding backend: {backend}")


def probe_openai_compatible_embedding_backend(
    *,
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout_seconds: float = 5.0,
) -> int:
    return _infer_openai_compatible_embedding_dim(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )


def _infer_openai_compatible_embedding_dim(
    *,
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout_seconds: float = 5.0,
) -> int:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI-compatible embeddings require the 'openai' package."
        ) from exc

    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    elif base_url:
        kwargs["api_key"] = "EMPTY"

    client = OpenAI(timeout=timeout_seconds, max_retries=0, **kwargs)
    response = client.embeddings.create(
        model=model,
        input=["socitwin longterm embedding dim probe"],
    )
    if not response.data or not response.data[0].embedding:
        raise RuntimeError("embedding response is empty")
    return len(response.data[0].embedding)


def episode_to_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TypeError("episode record must be a mapping.")
    payload = dict(record)
    return _normalize_action_episode_payload(payload)


def payload_to_episode(payload: Mapping[str, Any]) -> ActionEpisodeLike:
    normalized_payload = episode_to_payload(payload)
    return normalized_payload  # type: ignore[return-value]


def _normalize_action_episode_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_ACTION_EPISODE_KEYS - payload.keys())
    if missing:
        raise ValueError(f"action episode missing required fields: {', '.join(missing)}")
    memory_kind = str(payload.get("memory_kind", "") or "").strip()
    if memory_kind != "action_episode":
        raise ValueError("memory_kind must be 'action_episode'.")
    query_source = str(payload.get("query_source", "") or "").strip()
    if query_source not in ALLOWED_QUERY_SOURCES:
        raise ValueError(f"Unsupported query_source: {query_source}")

    normalized = {
        "memory_kind": "action_episode",
        "agent_id": str(payload.get("agent_id", "") or ""),
        "step_id": int(payload.get("step_id")),
        "action_index": int(payload.get("action_index", 0)),
        "timestamp": float(payload.get("timestamp", 0.0)),
        "platform": str(payload.get("platform", "") or ""),
        "action_name": str(payload.get("action_name", "") or ""),
        "action_category": str(payload.get("action_category", "") or ""),
        "action_fact": str(payload.get("action_fact", "") or ""),
        "target_type": str(payload.get("target_type", "") or ""),
        "target_id": payload.get("target_id"),
        "target_snapshot": dict(payload.get("target_snapshot", {}) or {}),
        "target_visible_in_prompt": bool(payload.get("target_visible_in_prompt", False)),
        "target_resolution_status": str(payload.get("target_resolution_status", "") or ""),
        "execution_status": str(payload.get("execution_status", "") or ""),
        "local_context": dict(payload.get("local_context", {}) or {}),
        "authored_content": str(payload.get("authored_content", "") or ""),
        "state_changes": list(payload.get("state_changes", []) or []),
        "outcome": str(payload.get("outcome", "") or ""),
        "idle_step_gap": int(payload.get("idle_step_gap", 0) or 0),
        "topic": str(payload.get("topic", "") or ""),
        "query_source": query_source,
        "action_significance": str(payload.get("action_significance", "") or ""),
        "evidence_quality": str(payload.get("evidence_quality", "") or ""),
        "degraded_evidence": bool(payload.get("degraded_evidence", False)),
        "summary_text": str(payload.get("summary_text", "") or ""),
        "metadata": dict(payload.get("metadata", {}) or {}),
    }
    return json.loads(json.dumps(normalized, ensure_ascii=False, sort_keys=True))


def _episode_document(payload: Mapping[str, Any]) -> str:
    lines = [
        _labeled_line("Action", payload.get("action_fact") or payload.get("action_name")),
        _labeled_line("Action name", payload.get("action_name")),
        _labeled_line("Action category", payload.get("action_category")),
        _labeled_line("Topic", payload.get("topic")),
        _labeled_line("Target", _target_document_text(payload)),
        _labeled_line("Context", _local_context_document_text(payload)),
        _labeled_line("Authored content", payload.get("authored_content")),
        _labeled_line("State changes", payload.get("state_changes")),
        _labeled_line("Outcome", payload.get("outcome")),
        _labeled_line("Significance", payload.get("action_significance")),
        _labeled_line("Execution status", payload.get("execution_status")),
        _labeled_line("Target resolution", payload.get("target_resolution_status")),
        _labeled_line("Evidence quality", payload.get("evidence_quality")),
        _labeled_line("Summary", payload.get("summary_text")),
    ]
    return "\n".join(line for line in lines if line)


def _labeled_line(label: str, value: Any) -> str:
    text = _stringify(value).strip()
    if not text or text in {"[]", "{}"}:
        return ""
    return f"{label}: {text}"


def _target_document_text(payload: Mapping[str, Any]) -> str:
    target_snapshot = payload.get("target_snapshot", {}) or {}
    parts: list[str] = []
    target_type = str(payload.get("target_type", "") or "").strip()
    target_id = payload.get("target_id")
    if target_type or target_id is not None:
        parts.append(f"{target_type}:{target_id}")
    if isinstance(target_snapshot, Mapping):
        for key in ("summary", "content", "group_name"):
            value = str(target_snapshot.get(key, "") or "").strip()
            if value:
                parts.append(value)
                break
        author_id = target_snapshot.get("user_id")
        if author_id is not None:
            parts.append(f"author:{author_id}")
        evidence_quality = str(target_snapshot.get("evidence_quality", "") or "").strip()
        if evidence_quality:
            parts.append(f"evidence:{evidence_quality}")
        if bool(target_snapshot.get("degraded_evidence", False)):
            parts.append("degraded_evidence:true")
    elif target_snapshot:
        parts.append(_stringify(target_snapshot))
    return " | ".join(part for part in parts if part)


def _local_context_document_text(payload: Mapping[str, Any]) -> str:
    local_context = payload.get("local_context", {}) or {}
    if not isinstance(local_context, Mapping):
        return _stringify(local_context)
    parts: list[str] = []
    parent_post = local_context.get("parent_post", {}) or {}
    if isinstance(parent_post, Mapping):
        parent_summary = str(parent_post.get("summary", "") or "").strip()
        if parent_summary:
            parts.append(f"parent post: {parent_summary}")
    group = local_context.get("group", {}) or {}
    if isinstance(group, Mapping):
        group_summary = str(group.get("summary", "") or "").strip()
        if group_summary:
            parts.append(f"group: {group_summary}")
    if not parts and local_context:
        parts.append(_stringify(local_context))
    return " | ".join(part for part in parts if part)


def _episode_record_id(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _rerank_retrieved_payloads(
    payloads: list[ActionEpisodeLike],
    *,
    query: str,
    limit: int,
) -> list[ActionEpisodeLike]:
    normalized_query = (query or "").strip().lower()
    query_tokens = _tokenize(normalized_query)
    scored = []
    for payload in payloads:
        score = _score_action_episode(payload, normalized_query, query_tokens)
        if score <= 0:
            continue
        scored.append((score, float(payload["timestamp"]), payload))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [payload for _, _, payload in scored[:limit]]


def _score_action_episode(
    payload: Mapping[str, Any],
    normalized_query: str,
    query_tokens: list[str],
) -> int:
    score = 0
    for field, weight in ACTION_SCORING_WEIGHTS.items():
        text = _stringify(payload.get(field)).lower()
        if not text:
            continue
        if normalized_query and normalized_query in text:
            score += weight * 2
        score += weight * sum(1 for token in query_tokens if token in text)
    if bool(payload.get("degraded_evidence", False)):
        score = max(0, score - 2)
    return score


def _serialize_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    serialized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            serialized[str(key)] = value
        elif isinstance(value, list) and all(
            isinstance(item, (str, int, float, bool)) or item is None
            for item in value
        ):
            if not value:
                continue
            serialized[str(key)] = value
    serialized[SERIALIZED_PAYLOAD_KEY] = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    return serialized


def _deserialize_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    serialized = dict(payload)
    serialized_payload = serialized.get(SERIALIZED_PAYLOAD_KEY)
    if isinstance(serialized_payload, str) and serialized_payload.strip():
        return json.loads(serialized_payload)
    return serialized


def _agent_query_filter_kwargs(agent_id: str | int | None) -> dict[str, Any]:
    if agent_id is None:
        return {}
    return {"where": {"agent_id": {"$eq": str(agent_id)}}}


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "") if token.strip()]


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " | ".join(_stringify(item) for item in value if _stringify(item))
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _validate_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError("limit must be positive.")
