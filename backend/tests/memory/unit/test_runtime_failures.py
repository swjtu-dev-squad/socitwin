from app.memory.config import ProviderRuntimePresetConfig
from app.memory.runtime_failures import normalize_model_error


def test_normalize_model_error_prefers_structured_status_matcher() -> None:
    class ProviderError(RuntimeError):
        def __init__(self) -> None:
            super().__init__("irrelevant text")
            self.status_code = 413
            self.error_code = "context_length_exceeded"

    preset = ProviderRuntimePresetConfig(
        provider_error_matchers={
            "custom": {
                "structured": {
                    "status_codes": {"context_overflow": (413,)},
                    "error_codes": {"context_overflow": ("context_length_exceeded",)},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": ("normalized overflow",)
                },
                "raw_patterns": {
                    "context_overflow": ("Raw overflow",)
                },
            },
            "*": {
                "structured": {
                    "status_codes": {},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {},
                "raw_patterns": {},
            },
        }
    )

    normalized = normalize_model_error(
        ProviderError(),
        backend_family="custom",
        provider_preset=preset,
    )

    assert normalized.category == "context_overflow"
    assert normalized.matcher_source == "structured_status_code"
    assert normalized.provider_status_code == 413
    assert normalized.provider_error_code == "context_length_exceeded"


def test_normalize_model_error_detects_context_overflow_by_provider_matcher() -> None:
    normalized = normalize_model_error(
        RuntimeError("input length exceeds maximum context window"),
        backend_family="ollama",
        provider_preset=ProviderRuntimePresetConfig(),
    )

    assert normalized.category == "context_overflow"
    assert bool(normalized.matched_pattern) is True
    assert normalized.matcher_source == "normalized_pattern"
    assert normalized.backend_family == "ollama"


def test_normalize_model_error_classifies_timeout_before_unknown() -> None:
    normalized = normalize_model_error(
        RuntimeError("request timed out while waiting for upstream"),
        backend_family="openai",
        provider_preset=ProviderRuntimePresetConfig(),
    )

    assert normalized.category == "transport_timeout"
    assert normalized.matcher_source == "built_in_timeout"
