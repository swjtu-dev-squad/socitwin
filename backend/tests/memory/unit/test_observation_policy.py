from app.memory.observation_policy import DefaultObservationPolicy


def test_default_policy_extracts_entities_topics_and_anchors() -> None:
    policy = DefaultObservationPolicy()

    envelope = policy.build_perception_envelope(
        prompt_visible_snapshot={
            "posts": {
                "success": True,
                "posts": [
                    {
                        "post_id": 1,
                        "user_id": 9,
                        "summary": "First post content about AI systems",
                        "comments": [
                            {
                                "comment_id": 21,
                                "user_id": 12,
                                "summary": "comment",
                            }
                        ],
                    }
                ],
            },
            "groups": {
                "success": True,
                "all_groups": [
                    {
                        "group_id": 7,
                        "summary": "Group 7",
                    }
                ],
                "messages": [
                    {
                        "message_id": 31,
                        "group_id": 7,
                        "user_id": 12,
                        "summary": "group message",
                    }
                ],
            },
        },
        observation_prompt="ignored for default policy",
    )

    assert envelope.entities == [
        "post:1",
        "user:9",
        "comment:21",
        "user:12",
        "group:7",
        "group_message:31",
    ]
    assert envelope.topic == "First post content about AI systems"
    assert envelope.topics == [
        "First post content about AI systems",
        "Group 7",
    ]
    assert envelope.semantic_anchors == [
        "post#1: First post content about AI systems",
        "comment#21: comment",
        "group#7: Group 7",
        "group_message#31: group message",
    ]
    assert "posts" in envelope.snapshot
