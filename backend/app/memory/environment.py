from __future__ import annotations

import copy
from typing import Any

from oasis.social_agent.agent_environment import SocialEnvironment

from .config import ActionV1RuntimeSettings
from .observation_shaper import ObservationArtifact, ObservationShaper


class ActionV1SocialEnvironment(SocialEnvironment):
    def __init__(
        self,
        action,
        runtime_settings: ActionV1RuntimeSettings,
        actionable_tool_names: set[str] | None = None,
    ):
        super().__init__(action)
        self.runtime_settings = runtime_settings
        self.actionable_tool_names = actionable_tool_names or set()
        self.observation_shaper = ObservationShaper(runtime_settings)
        self.last_observation_artifact: ObservationArtifact | None = None
        self.last_raw_observation_payload: dict[str, Any] | None = None
        self.last_visible_observation_payload: dict[str, Any] | None = None
        self.last_prompt_visible_snapshot: dict[str, Any] | None = None
        self.last_observation_prompt: str = ""
        self.last_render_stats: dict[str, Any] = {}

    async def to_text_prompt(
        self,
        include_posts: bool = True,
        include_followers: bool = True,
        include_follows: bool = True,
    ) -> str:
        del include_followers, include_follows
        posts_payload = await self.action.refresh() if include_posts else {"success": False}
        groups_payload = await self.action.listen_from_group()
        raw_payload = {
            "posts": copy.deepcopy(posts_payload),
            "groups": copy.deepcopy(groups_payload),
        }
        artifact = self.observation_shaper.shape(
            posts_payload=posts_payload,
            groups_payload=groups_payload,
            current_agent_id=getattr(self.action, "agent_id", None),
        )
        self.publish_observation_artifact(artifact, raw_payload=raw_payload)
        return artifact.observation_prompt

    def publish_observation_artifact(
        self,
        artifact: ObservationArtifact,
        *,
        raw_payload: dict[str, Any] | None = None,
    ) -> None:
        self.last_observation_artifact = artifact
        if raw_payload is not None:
            self.last_raw_observation_payload = copy.deepcopy(raw_payload)
        self.last_visible_observation_payload = copy.deepcopy(artifact.visible_payload)
        self.last_prompt_visible_snapshot = copy.deepcopy(artifact.prompt_visible_snapshot)
        self.last_observation_prompt = artifact.observation_prompt
        self.last_render_stats = copy.deepcopy(artifact.render_stats)
