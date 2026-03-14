from __future__ import annotations

import asyncio
import os
from unittest.mock import patch
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
from oasis_dashboard.context_smoke import build_parser, run_context_smoke
from oasis_dashboard.real_oasis_engine_v3 import RealOASISEngineV3


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

    def test_update_memory_strips_assistant_think_blocks_when_enabled(self):
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.STUB,
            token_counter=HeuristicUnicodeTokenCounter(),
        )
        user_info = UserInfo(
            user_name="agent_2",
            name="Agent 2",
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
            strip_assistant_think_blocks=True,
            compression=compression_config_for_platform("reddit"),
        )
        agent = ContextSocialAgent(
            agent_id=2,
            user_info=user_info,
            model=model,
            available_actions=[ActionType.DO_NOTHING],
            context_settings=settings,
        )
        agent.update_memory(
            BaseMessage.make_assistant_message(
                role_name="assistant",
                content="<think>\nreasoning\n</think>\nFinal answer",
            ),
            OpenAIBackendRole.ASSISTANT,
        )
        assistant_records = [
            record
            for record in agent.memory.retrieve()
            if record.memory_record.role_at_backend
            == OpenAIBackendRole.ASSISTANT
        ]
        self.assertEqual(len(assistant_records), 1)
        self.assertEqual(
            assistant_records[0].memory_record.message.content,
            "Final answer",
        )

    def test_perform_action_by_llm_appends_no_think_suffix_when_configured(self):
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.STUB,
            token_counter=HeuristicUnicodeTokenCounter(),
        )
        user_info = UserInfo(
            user_name="agent_3",
            name="Agent 3",
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
            observation_instruction_suffix="/no_think",
            compression=compression_config_for_platform("reddit"),
        )
        agent = ContextSocialAgent(
            agent_id=3,
            user_info=user_info,
            model=model,
            available_actions=[ActionType.DO_NOTHING],
            context_settings=settings,
        )

        async def fake_to_text_prompt():
            return '{"posts":[]}'

        captured = {}

        async def fake_astep(message):
            captured["content"] = message.content
            return {"status": "ok"}

        agent.env.to_text_prompt = fake_to_text_prompt
        agent.astep = fake_astep

        result = asyncio.run(agent.perform_action_by_llm())
        self.assertEqual(result["status"], "ok")
        self.assertTrue(captured["content"].endswith("/no_think"))
        self.assertIn('{"posts":[]}', captured["content"])

    def test_engine_collects_context_metrics(self):
        class FakeMemory:
            def get_context(self):
                return [], 321

            def retrieve(self):
                return [object(), object(), object()]

        class FakeAgent:
            def __init__(self):
                self.env = type(
                    "Env",
                    (),
                    {
                        "last_render_stats": {
                            "chars_before": 1200,
                            "chars_after": 400,
                            "truncated_field_count": 2,
                            "placeholder_field_count": 1,
                            "comments_omitted_count": 3,
                            "groups_omitted_count": 4,
                        }
                    },
                )()
                self.memory = FakeMemory()

        engine = RealOASISEngineV3()
        engine.agents = [FakeAgent(), FakeAgent()]
        metrics = engine._collect_context_metrics()
        self.assertEqual(metrics["agent_count"], 2)
        self.assertEqual(metrics["avg_chars_before"], 1200)
        self.assertEqual(metrics["avg_chars_after"], 400)
        self.assertEqual(metrics["avg_context_tokens"], 321)
        self.assertEqual(metrics["avg_memory_records"], 3)
        self.assertGreaterEqual(metrics["avg_get_context_ms"], 0.0)
        self.assertGreaterEqual(metrics["avg_retrieve_ms"], 0.0)
        self.assertEqual(metrics["context_token_errors"], 0)
        self.assertEqual(metrics["memory_retrieve_errors"], 0)

    def test_engine_step_returns_context_metrics(self):
        class FakeMemory:
            def get_context(self):
                return [], 111

            def retrieve(self):
                return [object(), object()]

        class FakeAgent:
            def __init__(self):
                self.env = type(
                    "Env",
                    (),
                    {
                        "last_render_stats": {
                            "chars_before": 900,
                            "chars_after": 300,
                            "truncated_field_count": 1,
                            "placeholder_field_count": 0,
                            "comments_omitted_count": 2,
                            "groups_omitted_count": 0,
                        }
                    },
                )()
                self.memory = FakeMemory()

        class FakeAgentGraph:
            def __init__(self, agent):
                self._agent = agent

            def get_agents(self):
                return [(0, self._agent)]

        class FakeEnv:
            def __init__(self, agent):
                self.agent_graph = FakeAgentGraph(agent)

            async def step(self, batch_actions):
                return None

        engine = RealOASISEngineV3()
        fake_agent = FakeAgent()
        engine.env = FakeEnv(fake_agent)
        engine.agents = [fake_agent]
        engine.active_agents = 1
        engine.is_running = True
        engine._get_actual_post_count = lambda: 7
        engine._get_real_agent_actions = lambda: [{"kind": "noop"}]

        result = asyncio.run(engine.step())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["current_step"], 1)
        self.assertEqual(result["total_posts"], 7)
        self.assertIn("context_metrics", result)
        self.assertEqual(result["context_metrics"]["avg_context_tokens"], 111)
        self.assertEqual(len(engine.logs), 1)
        self.assertIn("context_metrics", engine.logs[0])

    def test_engine_initialize_and_multi_step_with_stub_runtime(self):
        class FakeEnv:
            def __init__(self, agent_graph):
                self.agent_graph = agent_graph

            async def reset(self):
                return None

            async def step(self, batch_actions):
                return None

        stub_model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.STUB,
            token_counter=HeuristicUnicodeTokenCounter(),
        )
        fake_runtime = type(
            "ResolvedRuntime",
            (),
            {
                "model": stub_model,
                "token_counter": HeuristicUnicodeTokenCounter(),
                "context_token_limit": 4096,
                "generation_max_tokens": 512,
                "observation_instruction_suffix": "",
                "strip_assistant_think_blocks": False,
            },
        )()

        def fake_make(agent_graph, platform, database_path):
            del platform, database_path
            return FakeEnv(agent_graph)

        engine = RealOASISEngineV3(db_path="/tmp/oasis-dashboard-test.db")
        with patch(
            "oasis_dashboard.real_oasis_engine_v3.build_shared_model",
            return_value=fake_runtime,
        ), patch(
            "oasis_dashboard.real_oasis_engine_v3.make",
            side_effect=fake_make,
        ):
            init_result = asyncio.run(
                engine.initialize(
                    agent_count=2,
                    platform="reddit",
                    topics=["AI"],
                    regions=["General"],
                )
            )

        self.assertEqual(init_result["status"], "ok")
        self.assertEqual(init_result["context_token_limit"], 4096)
        self.assertEqual(init_result["generation_max_tokens"], 512)
        self.assertIsNone(init_result["memory_window_size"])
        self.assertEqual(len(engine.agents), 2)
        self.assertTrue(all(isinstance(agent, ContextSocialAgent) for agent in engine.agents))

        for agent in engine.agents:
            agent.env.last_render_stats = {
                "chars_before": 600,
                "chars_after": 240,
                "truncated_field_count": 1,
                "placeholder_field_count": 0,
                "comments_omitted_count": 2,
                "groups_omitted_count": 0,
            }

        engine._get_actual_post_count = lambda: 5
        engine._get_real_agent_actions = lambda: [{"kind": "noop"}]

        first = asyncio.run(engine.step())
        second = asyncio.run(engine.step())

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertEqual(first["current_step"], 1)
        self.assertEqual(second["current_step"], 2)
        self.assertEqual(first["context_metrics"]["agent_count"], 2)
        self.assertEqual(second["context_metrics"]["agent_count"], 2)
        self.assertEqual(second["context_metrics"]["avg_chars_after"], 240)
        self.assertEqual(len(engine.logs), 2)

    def test_engine_builds_qwen3_local_vllm_compat_spec_from_env(self):
        engine = RealOASISEngineV3(
            model_platform="vllm",
            model_type="qwen3-4b-awq",
        )
        with patch.dict(
            os.environ,
            {
                "OASIS_QWEN3_VLLM_LOCAL_COMPAT": "1",
                "OASIS_MODEL_CONTEXT_WINDOW": "8192",
            },
            clear=False,
        ):
            spec = engine._build_model_runtime_spec()

        self.assertIsInstance(spec, ModelRuntimeSpec)
        self.assertEqual(spec.observation_instruction_suffix, "/no_think")
        self.assertTrue(spec.strip_assistant_think_blocks)
        self.assertEqual(spec.declared_context_window, 8192)
        self.assertEqual(spec.model_config_dict["temperature"], 0.7)
        self.assertEqual(spec.model_config_dict["top_p"], 0.8)
        self.assertEqual(spec.model_config_dict["presence_penalty"], 1.5)
        self.assertEqual(spec.model_config_dict["extra_body"]["top_k"], 20)

    def test_context_smoke_runner_collects_steps(self):
        class FakeEngine:
            def __init__(self, model_platform, model_type, db_path):
                self.model_platform = model_platform
                self.model_type = model_type
                self.db_path = db_path
                self.reset_called = False
                self.step_count = 0

            async def initialize(
                self,
                agent_count,
                platform,
                recsys,
                topic,
                topics,
                regions,
            ):
                return {
                    "status": "ok",
                    "agent_count": agent_count,
                    "platform": platform,
                    "topics": topics or [topic],
                    "regions": regions or ["General"],
                    "context_token_limit": 4096,
                    "generation_max_tokens": 512,
                    "memory_window_size": 64,
                    "observation_instruction_suffix": "/no_think",
                }

            async def step(self):
                self.step_count += 1
                return {
                    "status": "ok",
                    "current_step": self.step_count,
                    "total_posts": 10 + self.step_count,
                    "step_time": 0.25,
                    "context_metrics": {
                        "avg_context_tokens": 222,
                        "max_context_tokens": 333,
                        "avg_memory_records": 4,
                        "avg_retrieve_ms": 1.25,
                    },
                }

            async def reset(self):
                self.reset_called = True
                return {"status": "ok"}

        args = build_parser().parse_args(
            [
                "--model-platform",
                "ollama",
                "--model-type",
                "qwen3:8b",
                "--agent-count",
                "2",
                "--steps",
                "2",
                "--platform",
                "reddit",
                "--topics",
                "AI",
                "--regions",
                "General",
            ]
        )
        with patch(
            "oasis_dashboard.context_smoke.RealOASISEngineV3",
            FakeEngine,
        ):
            result = asyncio.run(run_context_smoke(args))

        self.assertEqual(result["init"]["agent_count"], 2)
        self.assertEqual(result["init"]["memory_window_size"], 64)
        self.assertEqual(result["init"]["observation_instruction_suffix"], "/no_think")
        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(result["steps"][1]["step"], 2)
        self.assertEqual(
            result["steps"][1]["context_metrics"]["avg_context_tokens"], 222
        )


if __name__ == "__main__":
    unittest.main()
