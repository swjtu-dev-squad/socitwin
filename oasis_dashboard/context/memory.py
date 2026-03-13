from __future__ import annotations

from camel.memories import ChatHistoryMemory, ScoreBasedContextCreator
from camel.utils import BaseTokenCounter


def build_chat_history_memory(
    *,
    token_counter: BaseTokenCounter,
    context_token_limit: int,
    agent_id: str,
) -> ChatHistoryMemory:
    return ChatHistoryMemory(
        ScoreBasedContextCreator(token_counter, context_token_limit),
        window_size=None,
        agent_id=agent_id,
    )
