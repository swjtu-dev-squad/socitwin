from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .config import ProviderRuntimePresetConfig


@dataclass(slots=True)
class NormalizedModelError:
    category: str
    message: str
    original_exception: Exception
    backend_family: str = ""
    provider_status_code: int | None = None
    provider_error_code: str = ""
    raw_error_snippet: str = ""
    matched_pattern: str = ""
    matcher_source: str = ""


class ActionV1RuntimeError(RuntimeError):
    def __init__(
        self,
        *,
        category: str,
        reason: str,
        step_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(reason)
        self.category = category
        self.reason = reason
        self.step_id = step_id
        self.details = details or {}


class ContextBudgetExhaustedError(ActionV1RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        step_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            category="context_budget_exhausted",
            reason=reason,
            step_id=step_id,
            details=details,
        )


TIMEOUT_PATTERNS = ("timed out", "timeout", "time out")
NETWORK_PATTERNS = (
    "connection refused",
    "connection error",
    "temporary failure in name resolution",
    "dns",
    "socket",
    "network is unreachable",
)
RATE_LIMIT_PATTERNS = ("rate limit", "too many requests", "quota")
SERVICE_PATTERNS = (
    "service unavailable",
    "temporarily unavailable",
    "backend overload",
    "server error",
    "bad gateway",
    "gateway timeout",
)
AUTH_PATTERNS = (
    "unauthorized",
    "forbidden",
    "api key",
    "authentication",
    "model not found",
    "no such model",
)
SCHEMA_PATTERNS = (
    "invalid request",
    "validation error",
    "tool schema",
    "schema",
    "malformed",
    "bad request",
)


def normalize_model_error(
    exc: Exception,
    *,
    backend_family: str,
    provider_preset: ProviderRuntimePresetConfig,
) -> NormalizedModelError:
    message = _exception_message(exc)
    lowered = message.lower()
    normalized_backend_family = (backend_family or "").strip().lower()
    provider_status_code = _extract_status_code(exc)
    provider_error_code = _extract_error_code(exc)
    raw_error_snippet = message[:240]

    provider_match = _match_provider_category(
        exc=exc,
        backend_family=normalized_backend_family,
        provider_status_code=provider_status_code,
        provider_error_code=provider_error_code,
        provider_preset=provider_preset,
        lowered_message=lowered,
        raw_message=message,
    )
    if provider_match is not None:
        return NormalizedModelError(
            category=provider_match["category"],
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matched_pattern=provider_match.get("matched_pattern", ""),
            matcher_source=provider_match.get("matcher_source", ""),
        )

    if isinstance(exc, TimeoutError) or any(pattern in lowered for pattern in TIMEOUT_PATTERNS):
        return NormalizedModelError(
            category="transport_timeout",
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matcher_source="built_in_timeout",
        )
    if any(pattern in lowered for pattern in NETWORK_PATTERNS):
        return NormalizedModelError(
            category="transport_network",
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matcher_source="built_in_network",
        )
    if "429" in lowered or any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS):
        return NormalizedModelError(
            category="rate_limited",
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matcher_source="built_in_rate_limit",
        )
    if any(pattern in lowered for pattern in SERVICE_PATTERNS) or any(
        status in lowered for status in ("500", "502", "503", "504")
    ):
        return NormalizedModelError(
            category="service_unavailable",
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matcher_source="built_in_service",
        )
    if any(pattern in lowered for pattern in AUTH_PATTERNS):
        return NormalizedModelError(
            category="auth_or_config",
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matcher_source="built_in_auth",
        )
    if any(pattern in lowered for pattern in SCHEMA_PATTERNS):
        return NormalizedModelError(
            category="schema_or_request_invalid",
            message=message,
            original_exception=exc,
            backend_family=normalized_backend_family,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            raw_error_snippet=raw_error_snippet,
            matcher_source="built_in_schema",
        )

    return NormalizedModelError(
        category="unknown_model_error",
        message=message,
        original_exception=exc,
        backend_family=normalized_backend_family,
        provider_status_code=provider_status_code,
        provider_error_code=provider_error_code,
        raw_error_snippet=raw_error_snippet,
        matcher_source="unknown",
    )


def _match_provider_category(
    *,
    exc: Exception,
    backend_family: str,
    provider_status_code: int | None,
    provider_error_code: str,
    provider_preset: ProviderRuntimePresetConfig,
    lowered_message: str,
    raw_message: str,
) -> dict[str, str] | None:
    exception_type_names = {
        cls.__name__.lower() for cls in type(exc).__mro__ if cls is not object
    }
    normalized_error_code = provider_error_code.strip().lower()
    lowered_raw_message = raw_message.lower()
    for family_key in (backend_family, "*"):
        family_matchers = provider_preset.provider_error_matchers.get(family_key, {})
        structured = family_matchers.get("structured", {}) or {}

        for category, values in (structured.get("status_codes", {}) or {}).items():
            if provider_status_code is not None and provider_status_code in values:
                return {
                    "category": str(category),
                    "matched_pattern": str(provider_status_code),
                    "matcher_source": "structured_status_code",
                }
        for category, values in (structured.get("error_codes", {}) or {}).items():
            if normalized_error_code and normalized_error_code in {
                str(value).strip().lower() for value in values
            }:
                return {
                    "category": str(category),
                    "matched_pattern": normalized_error_code,
                    "matcher_source": "structured_error_code",
                }
        for category, values in (structured.get("exception_types", {}) or {}).items():
            normalized_values = {str(value).strip().lower() for value in values}
            matched_exception = next(
                (
                    exception_name
                    for exception_name in exception_type_names
                    if exception_name in normalized_values
                ),
                None,
            )
            if matched_exception is not None:
                return {
                    "category": str(category),
                    "matched_pattern": matched_exception,
                    "matcher_source": "structured_exception_type",
                }
        for category, values in (family_matchers.get("normalized_patterns", {}) or {}).items():
            for pattern in values:
                normalized_pattern = str(pattern).strip().lower()
                if normalized_pattern and normalized_pattern in lowered_message:
                    return {
                        "category": str(category),
                        "matched_pattern": normalized_pattern,
                        "matcher_source": "normalized_pattern",
                    }
        for category, values in (family_matchers.get("raw_patterns", {}) or {}).items():
            for pattern in values:
                raw_pattern = str(pattern).strip()
                if raw_pattern and raw_pattern.lower() in lowered_raw_message:
                    return {
                        "category": str(category),
                        "matched_pattern": raw_pattern,
                        "matcher_source": "raw_pattern",
                    }
    return None


def _extract_status_code(exc: Exception) -> int | None:
    candidates = (
        getattr(exc, "status_code", None),
        getattr(exc, "http_status", None),
        getattr(exc, "status", None),
        getattr(getattr(exc, "response", None), "status_code", None),
        getattr(getattr(exc, "response", None), "status", None),
    )
    for candidate in candidates:
        try:
            if candidate is not None:
                return int(candidate)
        except (TypeError, ValueError):
            continue

    payload = _extract_error_payload(exc)
    for key in ("status_code", "status"):
        value = payload.get(key)
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _extract_error_code(exc: Exception) -> str:
    candidates = (
        getattr(exc, "error_code", None),
        getattr(exc, "code", None),
        getattr(getattr(exc, "response", None), "error_code", None),
        getattr(getattr(exc, "response", None), "code", None),
    )
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text

    payload = _extract_error_payload(exc)
    for key in ("error_code", "code", "type"):
        text = str(payload.get(key, "") or "").strip()
        if text:
            return text
    return ""


def _extract_error_payload(exc: Exception) -> Mapping[str, Any]:
    for attr_name in ("body", "response_body", "error", "detail"):
        payload = getattr(exc, attr_name, None)
        if isinstance(payload, Mapping):
            return payload
    response = getattr(exc, "response", None)
    if isinstance(response, Mapping):
        return response
    return {}


def _exception_message(exc: Exception) -> str:
    message = str(exc or "").strip()
    if message:
        return message
    return exc.__class__.__name__
