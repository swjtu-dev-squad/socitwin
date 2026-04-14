from __future__ import annotations

from typing import Any

from oasis import AgentGraph, SocialAgent
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType


def build_upstream_social_agent(
    *,
    agent_id: int,
    user_info: UserInfo,
    agent_graph: AgentGraph,
    model: Any,
    available_actions: list[ActionType],
) -> SocialAgent:
    """Construct a plain upstream OASIS social agent."""

    return SocialAgent(
        agent_id=agent_id,
        user_info=user_info,
        agent_graph=agent_graph,
        model=model,
        available_actions=available_actions,
    )
