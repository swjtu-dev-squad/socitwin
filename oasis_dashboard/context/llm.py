from __future__ import annotations

from typing import Iterable

from camel.configs import (
    ChatGPTConfig,
    DeepSeekConfig,
    OllamaConfig,
    OpenRouterConfig,
    VLLMConfig,
)
from camel.models import ModelFactory, ModelManager
from camel.types import ModelPlatformType

from .config import ModelRuntimeSpec, ResolvedModelRuntime
from .tokens import HeuristicUnicodeTokenCounter


def build_shared_model(
    spec: ModelRuntimeSpec | list[ModelRuntimeSpec],
) -> ResolvedModelRuntime:
    specs = spec if isinstance(spec, list) else [spec]
    if not specs:
        raise ValueError("At least one model runtime spec is required.")

    _validate_homogeneous_specs(specs)
    backends = [_build_backend(item) for item in specs]
    token_counter = _resolve_token_counter(backends[0], specs[0])
    context_token_limit = _resolve_context_token_limit(specs[0])
    generation_max_tokens = specs[0].generation_max_tokens

    model = (
        backends[0]
        if len(backends) == 1
        else ModelManager(backends, scheduling_strategy="round_robin")
    )
    return ResolvedModelRuntime(
        model=model,
        token_counter=token_counter,
        context_token_limit=context_token_limit,
        generation_max_tokens=generation_max_tokens,
    )


def _build_backend(spec: ModelRuntimeSpec):
    platform = _normalize_platform(spec.model_platform)
    model_config_dict = _build_model_config(spec)
    return ModelFactory.create(
        model_platform=platform,
        model_type=spec.model_type,
        model_config_dict=model_config_dict,
        token_counter=spec.token_counter,
        api_key=spec.api_key,
        url=spec.url,
        timeout=spec.timeout,
        max_retries=spec.max_retries,
    )


def _resolve_token_counter(backend, spec: ModelRuntimeSpec):
    if spec.token_counter is not None:
        return spec.token_counter

    try:
        return backend.token_counter
    except Exception:
        fallback = HeuristicUnicodeTokenCounter()
        if hasattr(backend, "_token_counter"):
            backend._token_counter = fallback
        return fallback


def _resolve_context_token_limit(spec: ModelRuntimeSpec) -> int:
    if spec.context_token_limit is not None:
        return spec.context_token_limit
    if spec.declared_context_window is not None:
        generation = spec.generation_max_tokens or 512
        return max(1024, spec.declared_context_window - generation - 256)
    return 4096


def _build_model_config(spec: ModelRuntimeSpec) -> dict:
    config = _default_model_config(spec.model_platform)
    config.update(spec.model_config_dict)
    if spec.generation_max_tokens is not None:
        config["max_tokens"] = spec.generation_max_tokens
    return config


def _default_model_config(model_platform: str) -> dict:
    normalized = model_platform.lower()
    if normalized == "ollama":
        return OllamaConfig().as_dict()
    if normalized == "vllm":
        return VLLMConfig().as_dict()
    if normalized == "openai":
        return ChatGPTConfig().as_dict()
    if normalized == "openrouter":
        return OpenRouterConfig().as_dict()
    if normalized == "deepseek":
        return DeepSeekConfig().as_dict()
    return {}


def _normalize_platform(model_platform: str) -> ModelPlatformType:
    return ModelPlatformType(model_platform.lower())


def _validate_homogeneous_specs(specs: Iterable[ModelRuntimeSpec]) -> None:
    specs = list(specs)
    first = specs[0]
    for item in specs[1:]:
        if item.model_platform.lower() != first.model_platform.lower():
            raise ValueError("All pooled models must use the same platform.")
        if item.model_type != first.model_type:
            raise ValueError("All pooled models must use the same model_type.")
        if _resolve_context_token_limit(item) != _resolve_context_token_limit(
            first
        ):
            raise ValueError(
                "All pooled models must share the same context_token_limit."
            )
