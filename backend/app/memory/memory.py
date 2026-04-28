from __future__ import annotations

import time

from camel.memories import ChatHistoryMemory, MemoryRecord, ScoreBasedContextCreator
from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from .config import ActionV1RuntimeSettings


class ContextChatHistoryMemory(ChatHistoryMemory):
    def load_memory_records(self) -> list[MemoryRecord]:
        record_dicts = self._chat_history_block.storage.load()
        return [MemoryRecord.from_dict(record) for record in record_dicts]

    def replace_memory_records(self, records: list[MemoryRecord]) -> None:
        self._chat_history_block.storage.clear()
        self.write_records(records)

    def clean_tool_calls(self) -> None:
        records = self.load_memory_records()
        if not records:
            return

        cleaned_records = []
        for record in records:
            role = record.role_at_backend
            message = record.message
            message_class = message.__class__.__name__
            message_meta = message.meta_dict or {}

            if role in (OpenAIBackendRole.FUNCTION, OpenAIBackendRole.TOOL):
                continue
            if role == OpenAIBackendRole.ASSISTANT and (
                "tool_calls" in message_meta or message_class == "FunctionCallingMessage"
            ):
                continue
            cleaned_records.append(record)

        self.replace_memory_records(cleaned_records)

    def replace_tagged_user_records(
        self,
        *,
        since_index: int,
        tag_key: str,
        tag_value: str,
        summary_message: BaseMessage,
        summary_role: OpenAIBackendRole = OpenAIBackendRole.USER,
        timestamp: float | None = None,
    ) -> bool:
        record_dicts = self._chat_history_block.storage.load()
        if not record_dicts:
            return False

        prefix = record_dicts[: max(0, since_index)]
        suffix = record_dicts[max(0, since_index) :]

        matched_records = []
        rewritten_suffix = []
        inserted_summary = False

        for record in suffix:
            message = record.get("message", {})
            message_meta = message.get("meta_dict") or {}
            tag = message_meta.get(tag_key, message.get(tag_key))

            if (
                record.get("role_at_backend") == OpenAIBackendRole.USER.value
                and tag == tag_value
            ):
                matched_records.append(record)
                continue

            if matched_records and not inserted_summary:
                rewritten_suffix.append(
                    self._build_summary_record_dict(
                        matched_records=matched_records,
                        summary_message=summary_message,
                        summary_role=summary_role,
                        timestamp=timestamp,
                    )
                )
                inserted_summary = True

            rewritten_suffix.append(record)

        if matched_records and not inserted_summary:
            rewritten_suffix.append(
                self._build_summary_record_dict(
                    matched_records=matched_records,
                    summary_message=summary_message,
                    summary_role=summary_role,
                    timestamp=timestamp,
                )
            )

        if not matched_records:
            return False

        self._chat_history_block.storage.clear()
        self._chat_history_block.storage.save(prefix + rewritten_suffix)
        return True

    def _build_summary_record_dict(
        self,
        *,
        matched_records: list[dict],
        summary_message: BaseMessage,
        summary_role: OpenAIBackendRole,
        timestamp: float | None,
    ) -> dict:
        first_record = matched_records[0]
        return MemoryRecord(
            message=summary_message,
            role_at_backend=summary_role,
            timestamp=(
                timestamp if timestamp is not None else first_record.get("timestamp", time.time_ns() / 1_000_000_000)
            ),
            agent_id=first_record.get("agent_id") or self.agent_id or "",
        ).to_dict()


def build_chat_history_memory(
    *,
    token_counter,
    context_token_limit: int,
    agent_id: str,
    window_size: int | None = None,
) -> ContextChatHistoryMemory:
    return ContextChatHistoryMemory(
        ScoreBasedContextCreator(token_counter, context_token_limit),
        window_size=window_size,
        agent_id=agent_id,
    )


def build_runtime_memory(
    *,
    runtime_settings: ActionV1RuntimeSettings,
    agent_id: str,
):
    return build_chat_history_memory(
        token_counter=runtime_settings.token_counter,
        context_token_limit=runtime_settings.context_token_limit,
        agent_id=agent_id,
        window_size=runtime_settings.memory_window_size,
    )
