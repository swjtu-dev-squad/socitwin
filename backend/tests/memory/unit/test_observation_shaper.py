from camel.messages import BaseMessage

from app.memory.config import ActionV1RuntimeSettings, ObservationPresetConfig
from app.memory.observation_shaper import ObservationShaper


class DummyTokenCounter:
    def count_tokens_from_messages(self, messages) -> int:
        total = 0
        for message in messages:
            total += len(str(message.get("content", "")))
        return total


def build_settings(context_limit: int = 5000) -> ActionV1RuntimeSettings:
    return ActionV1RuntimeSettings(
        token_counter=DummyTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="system prompt",
        ),
        context_token_limit=context_limit,
        observation_preset=ObservationPresetConfig(),
    )


def test_observation_shaper_applies_comment_and_message_guards() -> None:
    settings = build_settings()
    settings.observation_preset.comments_total_guard = 2
    settings.observation_preset.messages_total_guard = 2
    settings.observation_preset.groups_count_guard = 1
    shaper = ObservationShaper(settings)

    posts_payload = {
        "success": True,
        "posts": [
            {
                "post_id": 1,
                "user_id": 10,
                "content": "post",
                "comments": [
                    {"comment_id": 1, "user_id": 11, "content": "c1"},
                    {"comment_id": 2, "user_id": 12, "content": "c2"},
                    {"comment_id": 3, "user_id": 13, "content": "c3"},
                ],
            }
        ],
    }
    groups_payload = {
        "success": True,
        "all_groups": {1: "group one", 2: "group two"},
        "joined_groups": [1, 2],
        "messages": {
            1: [{"message_id": 1, "content": "m1"}, {"message_id": 2, "content": "m2"}],
            2: [{"message_id": 3, "content": "m3"}],
        },
    }

    artifact = shaper.shape(
        posts_payload=posts_payload,
        groups_payload=groups_payload,
        current_agent_id=10,
    )

    assert artifact.visible_payload["posts"]["posts"][0]["comments_omitted_count"] == 1
    assert len(artifact.visible_payload["groups"]["all_groups"]) == 1
    assert artifact.render_stats["raw_guard_applied"] is True


def test_observation_shaper_enters_physical_fallback_under_tight_budget() -> None:
    settings = build_settings(context_limit=120)
    shaper = ObservationShaper(settings)

    posts_payload = {
        "success": True,
        "posts": [
            {
                "post_id": 1,
                "user_id": 10,
                "content": "x" * 500,
                "comments": [{"comment_id": 1, "user_id": 11, "content": "y" * 300}],
            }
        ],
    }
    groups_payload = {
        "success": True,
        "all_groups": {1: "group one"},
        "joined_groups": [1],
        "messages": {1: [{"message_id": 1, "content": "z" * 300}]},
    }

    artifact = shaper.shape(
        posts_payload=posts_payload,
        groups_payload=groups_payload,
        current_agent_id=10,
    )

    assert artifact.render_stats["final_shaping_stage"] == "physical_fallback"
    assert "group_count" in artifact.visible_payload["groups"]["all_groups"]
    assert "message_count" in artifact.visible_payload["groups"]["messages"]
