import type { SimulationStatus } from './types';

export function normalizeSimulationStatus(raw: Partial<SimulationStatus> | any): SimulationStatus {
  const state = raw?.state;
  return {
    ...raw,
    state,
    running: typeof raw?.running === 'boolean' ? raw.running : state === 'running',
    paused: typeof raw?.paused === 'boolean' ? raw.paused : state === 'paused',
    originalState: raw?.originalState ?? state,
    currentStep: raw?.currentStep ?? raw?.current_step ?? 0,
    currentRound: raw?.currentRound ?? raw?.current_round,
    activeAgents: raw?.activeAgents ?? raw?.active_agents ?? 0,
    totalPosts: raw?.totalPosts ?? raw?.total_posts ?? 0,
    totalInteractions: raw?.totalInteractions ?? raw?.total_interactions,
    agentCount: raw?.agentCount ?? raw?.agent_count,
    totalSteps: raw?.totalSteps ?? raw?.total_steps,
    memoryMode: raw?.memoryMode ?? raw?.memory_mode,
    contextTokenLimit: raw?.contextTokenLimit ?? raw?.context_token_limit,
    generationMaxTokens: raw?.generationMaxTokens ?? raw?.generation_max_tokens,
    modelBackendTokenLimit: raw?.modelBackendTokenLimit ?? raw?.model_backend_token_limit,
    agents: raw?.agents ?? [],
    polarization: raw?.polarization ?? 0,
  };
}
