from __future__ import annotations

import asyncio
import unittest

from camel.messages import BaseMessage
from camel.models import ModelFactory, ModelManager
from camel.types import ModelPlatformType, ModelType, OpenAIBackendRole
from oasis import ActionType, UserInfo

from oasis_dashboard.context import (
    ContextRuntimeSettings,
    ContextSocialAgent,
    ModelRuntimeSpec,
    build_shared_model,
)
from oasis_dashboard.context.config import compression_config_for_platform
from oasis_dashboard.context.environment import ContextSocialEnvironment
from oasis_dashboard.context.tokens import HeuristicUnicodeTokenCounter


class FakeAction:
    async def refresh(self):
        return {
            "success": True,
            "posts": [
                {
                    "post_id": 1,
                    "user_id": 7,
                    "content": "测试😀你好世界" * 80,
                    "created_at": "now",
                    "score": 3,
                    "num_shares": 0,
                    "num_reports": 0,
                    "comments": [
                        {
                            "comment_id": 1,
                            "post_id": 1,
                            "user_id": 8,
                            "content": "评论内容" * 40,
                            "created_at": "now",
                            "score": 2,
                        }
                    ],
                }
            ],
        }

    async def listen_from_group(self):
        return {
            "success": True,
            "all_groups": {1: "群组一"},
            "joined_groups": [1],
            "messages": {1: [{"message_id": 1, "content": "群聊消息" * 50}]},
        }


class ContextIntegrationTests(unittest.TestCase):
    def test_runtime_settings_validate(self):
        settings = ContextRuntimeSettings(
            token_counter=HeuristicUnicodeTokenCounter(),
            system_message=BaseMessage.make_assistant_message(
                role_name="system",
                content="system prompt",
            ),
            context_token_limit=4096,
            observation_soft_limit=3072,
            observation_hard_limit=4096,
            compression=compression_config_for_platform("reddit"),
        )
        settings.validate()

    def test_build_shared_model_pool_returns_model_manager(self):
        specs = [
            ModelRuntimeSpec(
                model_platform="ollama",
                model_type="qwen3:8b",
                url="http://localhost:11434/v1",
                token_counter=HeuristicUnicodeTokenCounter(),
            ),
            ModelRuntimeSpec(
                model_platform="ollama",
                model_type="qwen3:8b",
                url="http://localhost:11435/v1",
                token_counter=HeuristicUnicodeTokenCounter(),
            ),
        ]
        resolved = build_shared_model(specs)
        self.assertIsInstance(resolved.model, ModelManager)
        self.assertEqual(resolved.context_token_limit, 4096)

    def test_environment_uses_unescaped_unicode_json(self):
        settings = ContextRuntimeSettings(
            token_counter=HeuristicUnicodeTokenCounter(),
            system_message=BaseMessage.make_assistant_message(
                role_name="system",
                content="system prompt",
            ),
            context_token_limit=1024,
            observation_soft_limit=128,
            observation_hard_limit=1024,
            compression=compression_config_for_platform("reddit"),
        )
        env = ContextSocialEnvironment(
            action=FakeAction(),
            runtime_settings=settings,
            actionable_tool_names=set(),
        )
        prompt = asyncio.run(env.to_text_prompt())
        self.assertNotIn("\\u6d4b", prompt)
        self.assertIn('"group_count":1', prompt)
        self.assertIn('"comments_omitted_count":1', prompt)
        self.assertIn("[truncated from", prompt)

    def test_context_social_agent_replaces_env_and_preserves_system_message(self):
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.STUB,
            token_counter=HeuristicUnicodeTokenCounter(),
        )
        user_info = UserInfo(
            user_name="agent_0",
            name="Agent 0",
            description="desc",
            profile={
                "other_info": {
                    "user_profile": "profile",
                    "gender": "unknown",
                    "age": 25,
                    "mbti": "UNKNOWN",
                    "country": "General",
                }
            },
            recsys_type="reddit",
        )
        settings = ContextRuntimeSettings(
            token_counter=HeuristicUnicodeTokenCounter(),
            system_message=BaseMessage.make_assistant_message(
                role_name="system",
                content=user_info.to_system_message(),
            ),
            context_token_limit=4096,
            observation_soft_limit=3072,
            observation_hard_limit=4096,
            compression=compression_config_for_platform("reddit"),
        )
        agent = ContextSocialAgent(
            agent_id=0,
            user_info=user_info,
            model=model,
            available_actions=[
                ActionType.CREATE_POST,
                ActionType.LIKE_POST,
                ActionType.REFRESH,
                ActionType.DO_NOTHING,
            ],
            context_settings=settings,
        )
        self.assertIsInstance(agent.env, ContextSocialEnvironment)
        self.assertTrue(
            any(
                record.memory_record.role_at_backend
                == OpenAIBackendRole.SYSTEM
                for record in agent.memory.retrieve()
            )
        )
        first_tool = agent.action_tools[0]
        self.assertIs(first_tool.func.__self__, agent.env.action)

    def test_update_memory_accepts_positional_and_keyword_calls(self):
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.STUB,
            token_counter=HeuristicUnicodeTokenCounter(),
        )
        user_info = UserInfo(
            user_name="agent_1",
            name="Agent 1",
            description="desc",
            profile={
                "other_info": {
                    "user_profile": "profile",
                    "gender": "unknown",
                    "age": 25,
                    "mbti": "UNKNOWN",
                    "country": "General",
                }
            },
            recsys_type="reddit",
        )
        settings = ContextRuntimeSettings(
            token_counter=HeuristicUnicodeTokenCounter(),
            system_message=BaseMessage.make_assistant_message(
                role_name="system",
                content=user_info.to_system_message(),
            ),
            context_token_limit=4096,
            observation_soft_limit=3072,
            observation_hard_limit=4096,
            compression=compression_config_for_platform("reddit"),
        )
        agent = ContextSocialAgent(
            agent_id=1,
            user_info=user_info,
            model=model,
            available_actions=[ActionType.DO_NOTHING],
            context_settings=settings,
        )
        agent.update_memory(
            BaseMessage.make_user_message(role_name="User", content="hello"),
            OpenAIBackendRole.USER,
        )
        agent.update_memory(
            message=BaseMessage.make_user_message(
                role_name="User", content="world"
            ),
            role=OpenAIBackendRole.USER,
        )
        user_records = [
            record
            for record in agent.memory.retrieve()
            if record.memory_record.role_at_backend == OpenAIBackendRole.USER
        ]
        self.assertEqual(len(user_records), 2)


if __name__ == "__main__":
    unittest.main()
