"""从旧 oasis-dashboard.context.config 精简：仅保留 Persona LLM 所需的运行时规格类型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from camel.models import BaseModelBackend, ModelManager
from camel.utils import BaseTokenCounter


@dataclass(slots=True)
class ModelRuntimeSpec:
    model_platform: str
    model_type: str
    model_config_dict: dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: int = 3
    generation_max_tokens: Optional[int] = None
    declared_context_window: Optional[int] = None
    context_token_limit: Optional[int] = None
    token_counter: Optional[BaseTokenCounter] = None


@dataclass(slots=True)
class ResolvedModelRuntime:
    model: BaseModelBackend | ModelManager
    token_counter: BaseTokenCounter
    context_token_limit: int
    generation_max_tokens: Optional[int]
