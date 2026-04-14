"""Memory runtime entrypoints for Socitwin."""

from .action_capabilities import ActionCapability, ActionCapabilityRegistry
from .action_evidence import ActionEvidence, ActionEvidenceBuilder
from .config import (
    ActionV1RuntimeSettings,
    MemoryMode,
    MemoryRuntimeConfig,
    ObservationPresetConfig,
    ProviderRuntimePresetConfig,
    RecallPresetConfig,
    SummaryPresetConfig,
    WorkingMemoryBudgetConfig,
    resolve_memory_runtime_config,
)
from .consolidator import ConsolidationOutcome, Consolidator
from .episodic_memory import (
    ActionEpisode,
    EpisodeRecord,
    HeartbeatRange,
    PlatformMemoryAdapter,
    StepRecord,
    StepRecordKind,
    StepSegment,
    build_platform_memory_adapter,
)
from .environment import ActionV1SocialEnvironment
from .memory_rendering import CompressedNoteView, RecentTurnView
from .observation_shaper import ObservationArtifact, ObservationShaper
from .prompt_assembler import PromptAssembler, PromptAssemblyResult
from .recall_planner import RecallPlanner, RecallPreparation, RecallRuntimeState
from .retrieval_policy import RetrievalPolicy, RetrievalRequest
from .runtime_failures import (
    ActionV1RuntimeFailure,
    ContextBudgetExhaustedError,
    NormalizedModelError,
    normalize_model_error,
)
from .working_memory import (
    ActionItem,
    ActionSummaryBlock,
    CompressedWorkingMemory,
    MemoryState,
    RecentWorkingMemory,
)
from .runtime import MemoryRuntimeFacade, MemoryRuntimeNotImplementedError

__all__ = [
    "ActionCapability",
    "ActionCapabilityRegistry",
    "ActionEvidence",
    "ActionEvidenceBuilder",
    "ActionEpisode",
    "ActionItem",
    "ActionV1RuntimeSettings",
    "ActionV1SocialEnvironment",
    "ActionSummaryBlock",
    "CompressedNoteView",
    "CompressedWorkingMemory",
    "ConsolidationOutcome",
    "Consolidator",
    "EpisodeRecord",
    "HeartbeatRange",
    "MemoryMode",
    "MemoryRuntimeConfig",
    "MemoryRuntimeFacade",
    "MemoryRuntimeNotImplementedError",
    "MemoryState",
    "ObservationArtifact",
    "ObservationPresetConfig",
    "ObservationShaper",
    "PlatformMemoryAdapter",
    "PromptAssembler",
    "PromptAssemblyResult",
    "ProviderRuntimePresetConfig",
    "RecallPlanner",
    "RecallPreparation",
    "RecallPresetConfig",
    "RecallRuntimeState",
    "RecentTurnView",
    "RecentWorkingMemory",
    "ActionV1RuntimeFailure",
    "ContextBudgetExhaustedError",
    "NormalizedModelError",
    "RetrievalPolicy",
    "RetrievalRequest",
    "StepRecord",
    "StepRecordKind",
    "StepSegment",
    "SummaryPresetConfig",
    "WorkingMemoryBudgetConfig",
    "build_platform_memory_adapter",
    "normalize_model_error",
    "resolve_memory_runtime_config",
]
