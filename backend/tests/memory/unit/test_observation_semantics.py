from app.memory.observation_semantics import build_prompt_visible_snapshot


def test_prompt_visible_snapshot_tracks_self_authored_and_evidence_quality() -> None:
    snapshot = build_prompt_visible_snapshot(
        posts_payload={
            "success": True,
            "posts": [
                {
                    "post_id": 1,
                    "user_id": 7,
                    "content": "Important post summary ...[summarized from 420 chars]",
                    "comments": [
                        {
                            "comment_id": 21,
                            "post_id": 1,
                            "user_id": 8,
                            "content": "Short comment",
                        }
                    ],
                }
            ],
        },
        groups_payload={
            "success": True,
            "all_groups": {"3": "AI Safety Researchers"},
            "joined_groups": [3],
            "messages": {
                3: [
                    {
                        "message_id": 9,
                        "content": "[truncated from 300 chars]",
                    }
                ]
            },
        },
        current_agent_id=7,
    )

    post = snapshot["posts"]["posts"][0]
    comment = post["comments"][0]
    group = snapshot["groups"]["all_groups"][0]
    message = snapshot["groups"]["messages"][0]

    assert post["relation_anchor"] == "unknown"
    assert post["self_authored"] is True
    assert post["degraded_evidence"] is True
    assert post["evidence_quality"] == "degraded"
    assert comment["evidence_quality"] == "normal"
    assert comment["degraded_evidence"] is False
    assert comment["self_authored"] is False
    assert group["relation_anchor"] == "unknown"
    assert snapshot["groups"]["joined_group_ids"] == [3]
    assert message["degraded_evidence"] is True
    assert message["evidence_quality"] == "omitted"


def test_prompt_visible_snapshot_marks_self_authored_comment_and_group_message() -> None:
    snapshot = build_prompt_visible_snapshot(
        posts_payload={
            "success": True,
            "posts": [
                {
                    "post_id": 1,
                    "user_id": 99,
                    "content": "Other user's post",
                    "comments": [
                        {
                            "comment_id": 21,
                            "post_id": 1,
                            "user_id": 7,
                            "content": "My reply",
                        }
                    ],
                }
            ],
        },
        groups_payload={
            "success": True,
            "all_groups": {"3": "AI Safety Researchers"},
            "joined_groups": [3],
            "messages": {
                3: [
                    {
                        "message_id": 9,
                        "sender_id": 7,
                        "content": "My group message",
                    }
                ]
            },
        },
        current_agent_id=7,
    )

    post = snapshot["posts"]["posts"][0]
    comment = post["comments"][0]
    message = snapshot["groups"]["messages"][0]

    assert post["self_authored"] is False
    assert comment["self_authored"] is True
    assert message["self_authored"] is True
