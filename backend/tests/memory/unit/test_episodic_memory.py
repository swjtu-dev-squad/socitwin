from app.memory.episodic_memory import build_platform_memory_adapter


def test_format_action_fact_sorts_tool_args() -> None:
    adapter = build_platform_memory_adapter("reddit")

    action_fact = adapter.format_action_fact(
        tool_name="create_comment",
        tool_args={"post_id": 12, "content": "hello"},
    )

    assert action_fact == "create_comment(content=hello, post_id=12)"


def test_default_adapter_derives_reddit_state_changes() -> None:
    adapter = build_platform_memory_adapter("reddit")

    created_comment = adapter.derive_state_changes(
        tool_name="create_comment",
        tool_args={"post_id": 5},
        tool_result={"comment_id": 42, "success": True},
    )
    sent_message = adapter.derive_state_changes(
        tool_name="send_to_group",
        tool_args={"group_id": 9},
        tool_result={"message_id": 77, "success": True},
    )

    assert created_comment == ["created_comment:42"]
    assert sent_message == ["sent_group_message:77"]


def test_failed_tool_result_does_not_emit_state_changes() -> None:
    adapter = build_platform_memory_adapter("twitter")

    state_changes = adapter.derive_state_changes(
        tool_name="create_post",
        tool_args={},
        tool_result={"success": False, "error": "bad request"},
    )

    assert state_changes == []
