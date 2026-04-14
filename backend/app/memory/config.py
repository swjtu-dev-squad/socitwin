from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MemoryMode(str, Enum):
    """Supported memory runtimes in the new repository."""

    UPSTREAM = "upstream"
    ACTION_V1 = "action_v1"


@dataclass(slots=True)
class MemoryRuntimeConfig:
    """Minimal Phase-1 memory runtime configuration."""

    mode: MemoryMode = MemoryMode.UPSTREAM


def normalize_memory_mode(value: MemoryMode | str | None) -> MemoryMode:
    """Normalize explicit mode strings from API/config/env surfaces."""

    if isinstance(value, MemoryMode):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return MemoryMode.UPSTREAM
    try:
        return MemoryMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in MemoryMode)
        raise ValueError(
            f"Unsupported memory mode '{value}'. Expected one of: {allowed}."
        ) from exc


def resolve_memory_runtime_config(
    *,
    explicit_mode: MemoryMode | str | None = None,
    settings_mode: str | None = None,
) -> MemoryRuntimeConfig:
    """Resolve the Phase-1 runtime mode with explicit config taking priority."""

    if explicit_mode not in (None, ""):
        return MemoryRuntimeConfig(mode=normalize_memory_mode(explicit_mode))
    return MemoryRuntimeConfig(mode=normalize_memory_mode(settings_mode))
