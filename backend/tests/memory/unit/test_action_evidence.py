from app.memory.action_capabilities import ActionCapabilityRegistry
from app.memory.action_evidence import ActionEvidenceBuilder


def _empty_snapshot() -> dict:
    return {
        "posts": {"posts": []},
        "groups": {"all_groups": [], "joined_group_ids": [], "messages": []},
    }


def test_action_capability_registry_matches_current_longterm_scope() -> None:
    registry = ActionCapabilityRegistry()

    assert registry.is_eligible_for_longterm("like_post") is True
    assert registry.is_eligible_for_longterm("create_comment") is True
    assert registry.infer_target_reference(
        action_name="create_comment",
        tool_args={"post_id": 7, "content": "hello"},
    ) == ("post", 7)
    assert (
        registry.extract_authored_content(
            action_name="create_comment",
            tool_args={"post_id": 7, "content": "hello"},
        )
        == "hello"
    )
    assert registry.is_eligible_for_longterm("refresh") is False


def test_builder_resolves_visible_comment_with_parent_post_context() -> None:
    builder = ActionEvidenceBuilder()
    snapshot = {
        "posts": {
            "posts": [
                {
                    "object_kind": "post",
                    "post_id": 1,
                    "summary": "Parent post summary",
                    "relation_anchor": "unknown",
                    "comments": [
                        {
                            "object_kind": "comment",
                            "comment_id": 21,
                            "post_id": 1,
                            "summary": "Visible comment summary",
                            "relation_anchor": "unknown",
                        }
                    ],
                }
            ]
        },
        "groups": {"all_groups": [], "joined_group_ids": [], "messages": []},
    }

    evidence = builder.build(
        prompt_visible_snapshot=snapshot,
        action_name="like_comment",
        tool_args={"comment_id": 21},
        tool_result={"success": True},
    )

    assert evidence.target_type == "comment"
    assert evidence.target_visible_in_prompt is True
    assert evidence.target_resolution_status == "visible_in_prompt"
    assert evidence.execution_status == "success"
    assert evidence.target_snapshot["comment_id"] == 21
    assert evidence.local_context["parent_post"]["summary"] == "Parent post summary"
    assert evidence.eligible_for_longterm is True


def test_builder_marks_target_not_visible_without_fabricating_snapshot() -> None:
    builder = ActionEvidenceBuilder()

    evidence = builder.build(
        prompt_visible_snapshot=_empty_snapshot(),
        action_name="like_post",
        tool_args={"post_id": 99},
        tool_result={"success": False, "message": "Post not found"},
    )

    assert evidence.target_visible_in_prompt is False
    assert evidence.target_resolution_status == "invalid_target"
    assert evidence.execution_status == "hallucinated"
    assert evidence.target_snapshot == {}


def test_builder_marks_visible_target_that_expires_before_execution() -> None:
    builder = ActionEvidenceBuilder()
    snapshot = {
        "posts": {
            "posts": [
                {
                    "object_kind": "post",
                    "post_id": 5,
                    "summary": "A visible post",
                    "relation_anchor": "unknown",
                    "comments": [],
                }
            ]
        },
        "groups": {"all_groups": [], "joined_group_ids": [], "messages": []},
    }

    evidence = builder.build(
        prompt_visible_snapshot=snapshot,
        action_name="like_post",
        tool_args={"post_id": 5},
        tool_result={"success": False, "error": "Target ID not found"},
    )

    assert evidence.target_visible_in_prompt is True
    assert evidence.target_resolution_status == "expired_target"
    assert evidence.execution_status == "failed"


def test_builder_preserves_self_authored_fields_in_snapshot_and_parent_context() -> None:
    builder = ActionEvidenceBuilder()
    snapshot = {
        "posts": {
            "posts": [
                {
                    "object_kind": "post",
                    "post_id": 1,
                    "summary": "My parent post",
                    "relation_anchor": "unknown",
                    "self_authored": True,
                    "comments": [
                        {
                            "object_kind": "comment",
                            "comment_id": 21,
                            "post_id": 1,
                            "summary": "Visible comment summary",
                            "relation_anchor": "unknown",
                            "self_authored": False,
                        }
                    ],
                }
            ]
        },
        "groups": {"all_groups": [], "joined_group_ids": [], "messages": []},
    }

    post_evidence = builder.build(
        prompt_visible_snapshot=snapshot,
        action_name="like_post",
        tool_args={"post_id": 1},
        tool_result={"success": True},
    )
    comment_evidence = builder.build(
        prompt_visible_snapshot=snapshot,
        action_name="like_comment",
        tool_args={"comment_id": 21},
        tool_result={"success": True},
    )

    assert post_evidence.target_snapshot["self_authored"] is True
    assert comment_evidence.local_context["parent_post"]["self_authored"] is True
