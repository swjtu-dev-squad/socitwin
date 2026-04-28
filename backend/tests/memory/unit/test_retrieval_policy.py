from app.memory.episodic_memory import EpisodeQuerySource
from app.memory.retrieval_policy import RetrievalPolicy


def test_build_request_prefers_distilled_topic() -> None:
    policy = RetrievalPolicy()

    request = policy.build_request(
        topic="AI safety incident review",
        semantic_anchors=["post#1: ignored if topic exists"],
        entities=["post:1", "user:2"],
        limit=3,
    )

    assert request is not None
    assert request.query_source == EpisodeQuerySource.DISTILLED_TOPIC.value
    assert request.query_text == "AI safety incident review"
    assert request.limit == 3


def test_build_request_falls_back_to_structured_anchors() -> None:
    policy = RetrievalPolicy()

    request = policy.build_request(
        topic="",
        semantic_anchors=[
            "post#7: incident review summary",
            "group#2: safety working group",
            "comment#9: should be clipped from query",
        ],
        entities=["post:7", "user:5", "group:2"],
        limit=2,
    )

    assert request is not None
    assert request.query_source == EpisodeQuerySource.STRUCTURED_EVENT_QUERY.value
    assert (
        request.query_text
        == "post#7: incident review summary group#2: safety working group"
    )
    assert request.limit == 2


def test_build_request_falls_back_to_recent_action_episode_summary() -> None:
    policy = RetrievalPolicy()

    request = policy.build_request(
        topic="",
        semantic_anchors=[],
        entities=[],
        recent_episodes=[
            {
                "memory_kind": "action_episode",
                "action_name": "like_post",
                "target_snapshot": {"summary": "AI safety incident review"},
                "authored_content": "",
                "local_context": {},
                "outcome": "Acted on prior concern",
            },
            {
                "memory_kind": "action_episode",
                "action_name": "create_comment",
                "target_snapshot": {"summary": "Governance update"},
                "authored_content": "I disagree with this proposal",
                "local_context": {
                    "parent_post": {"summary": "Model governance thread"}
                },
                "outcome": "Final answer",
            },
        ],
        limit=2,
    )

    assert request is not None
    assert request.query_source == EpisodeQuerySource.RECENT_EPISODIC_SUMMARY.value
    assert "like_post" in request.query_text
    assert "AI safety incident review" in request.query_text
    assert "create_comment" in request.query_text
    assert "Model governance thread" in request.query_text
    assert "I disagree with this proposal" in request.query_text


def test_build_request_returns_none_without_query_material() -> None:
    policy = RetrievalPolicy()

    request = policy.build_request(
        topic="",
        semantic_anchors=[],
        entities=[],
        recent_episodes=[],
        limit=1,
    )

    assert request is None


def test_format_results_returns_readable_multiline_text() -> None:
    policy = RetrievalPolicy()

    text = policy.format_results(
        [
            {
                "step_id": 4,
                "platform": "reddit",
                "topic": "AI safety",
                "semantic_anchors": ["post#9: model evaluation thread"],
                "actions": ["like_post(post_id=9)"],
                "state_changes": ["liked_post:9"],
                "outcome": "Final answer",
            }
        ]
    )

    assert "Relevant long-term memory:" in text
    assert "Step 4 on reddit" in text
    assert "topic: AI safety" in text
    assert "anchors: post#9: model evaluation thread" in text
    assert "like_post(post_id=9)" in text
    assert "liked_post:9" in text
    assert "Final answer" in text
