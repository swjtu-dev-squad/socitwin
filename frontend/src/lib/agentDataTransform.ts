/**
 * Data Transformation Layer
 *
 * Transforms backend API responses to frontend data structures.
 * Backend API: /api/sim/status (from backend/app/models/simulation.py)
 * Frontend expects: enriched agent data with additional fields
 */

import type {
  AgentOverview,
  AgentMonitorResponse,
  AgentDetailResponse,
  AgentGraphNode,
  AgentGraphEdge,
  AgentMemorySnapshot,
} from './agentMonitorTypes';

// ============================================================================
// Backend Types (matching backend/app/models/simulation.py)
// ============================================================================

export interface BackendAgent {
  id: number;
  user_name: string;
  name: string;
  description: string;
  bio?: string;
  status: string;
  polarization: number;
  influence: number;
  activity: number;
  interests: string[];
}

export interface BackendSimulationStatus {
  state: string;
  current_step: number;
  total_steps: number;
  agent_count: number;
  platform: string;
  created_at?: string;
  updated_at?: string;
  total_posts: number;
  total_interactions: number;
  polarization: number;
  active_agents: number;
  agents: BackendAgent[];
  metrics_summary?: any;
}

// ============================================================================
// Transformation Functions
// ============================================================================

/**
 * Transform backend Agent to frontend AgentOverview
 */
export function transformToAgentOverview(
  backendAgent: BackendAgent
): AgentOverview {
  const role = deriveRoleFromDescription(backendAgent.description);
  const roleLabel = deriveRoleLabel(role, backendAgent.description);

  return {
    id: String(backendAgent.id),
    name: backendAgent.name,
    role,
    roleLabel,
    bio: backendAgent.bio || backendAgent.description || '',
    status: normalizeStatus(backendAgent.status),
    influence: backendAgent.influence,
    activity: backendAgent.activity,
    lastAction: null, // Backend doesn't provide this
    actionContent: undefined,
    country: undefined, // Backend doesn't provide this
    city: undefined, // Backend doesn't provide this
    occupation: undefined, // Backend doesn't provide this
    tags: backendAgent.interests || [],
    following: [], // Backend doesn't provide this
    followerCount: 0, // Backend doesn't provide this
    followingCount: 0, // Backend doesn't provide this
    interactionCount: 0, // Backend doesn't provide this
    memory: createEmptyMemorySnapshot(),
  };
}

/**
 * Transform backend SimulationStatus to frontend AgentMonitorResponse
 */
export function transformToMonitorResponse(
  backendStatus: BackendSimulationStatus
): AgentMonitorResponse {
  const agents = backendStatus.agents.map(transformToAgentOverview);
  const nodes = transformToGraphNodes(agents);
  const edges: AgentGraphEdge[] = []; // No edge data from backend

  return {
    simulation: {
      running: backendStatus.state === 'running',
      paused: backendStatus.state === 'paused',
      currentStep: backendStatus.current_step,
      currentRound: backendStatus.current_step
        ? Math.floor(backendStatus.current_step / 10)
        : undefined,
      platform: backendStatus.platform,
      recsys: undefined, // Backend doesn't provide this
      topic: undefined, // Backend doesn't provide this
      polarization: backendStatus.polarization,
      propagationVelocity: undefined, // Backend doesn't provide this
      herdIndex: undefined, // Backend doesn't provide this
    },
    graph: {
      nodes,
      edges,
    },
    agents,
    updatedAt: backendStatus.updated_at || new Date().toISOString(),
  };
}

/**
 * Create minimal AgentDetailResponse from backend data
 */
export function transformToAgentDetail(
  backendAgent: BackendAgent,
  _backendStatus?: BackendSimulationStatus
): AgentDetailResponse {
  const role = deriveRoleFromDescription(backendAgent.description);
  const roleLabel = deriveRoleLabel(role, backendAgent.description);

  return {
    profile: {
      id: String(backendAgent.id),
      name: backendAgent.name,
      bio: backendAgent.bio || backendAgent.description || '',
      personaKey: role,
      personaDescription: backendAgent.description || '',
      roleLabel,
      gender: undefined, // Backend doesn't provide this
      age: undefined, // Backend doesn't provide this
      mbti: undefined, // Backend doesn't provide this
      country: undefined, // Backend doesn't provide this
      city: undefined, // Backend doesn't provide this
      occupation: undefined, // Backend doesn't provide this
      tags: backendAgent.interests || [],
    },
    status: {
      state: normalizeStatus(backendAgent.status),
      influence: backendAgent.influence,
      activity: backendAgent.activity,
      followerCount: 0, // Backend doesn't provide this
      followingCount: 0, // Backend doesn't provide this
      interactionCount: 0, // Backend doesn't provide this
      polarization: backendAgent.polarization,
      contextTokens: undefined, // Backend doesn't provide this
      retrievedMemories: undefined, // Backend doesn't provide this
      seenAgentsCount: undefined, // Backend doesn't provide this
    },
    currentViewpoint: undefined, // Backend doesn't provide this
    lastAction: null, // Backend doesn't provide this
    recentTimeline: [], // Backend doesn't provide this
    seenPosts: [], // Backend doesn't provide this
    memory: createEmptyMemorySnapshot(),
  };
}

/**
 * Transform agents to graph nodes
 */
export function transformToGraphNodes(agents: AgentOverview[]): AgentGraphNode[] {
  return agents.map((agent) => ({
    id: agent.id,
    name: agent.name,
    role: agent.role,
    roleLabel: agent.roleLabel,
    influence: agent.influence,
    activity: agent.activity,
    status: agent.status,
    country: agent.country,
    city: agent.city,
  }));
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Derive agent role from description
 */
function deriveRoleFromDescription(description: string): string {
  const desc = description.toLowerCase();

  if (desc.includes('kol') || desc.includes('key opinion leader') || desc.includes('influencer')) {
    return 'KOL';
  }
  if (desc.includes('optimistic') || desc.includes('enthusiast') || desc.includes('supporter')) {
    return 'Evangelist';
  }
  if (desc.includes('skeptical') || desc.includes('critic') || desc.includes('doubter')) {
    return 'Skeptic';
  }
  if (desc.includes('neutral') || desc.includes('observer') || desc.includes('moderate')) {
    return 'Observer';
  }

  return 'Neutral';
}

/**
 * Derive role label for display
 */
function deriveRoleLabel(role: string, description: string): string {
  const roleLabels: Record<string, string> = {
    KOL: 'KOL',
    Evangelist: 'AI 乐观派',
    Skeptic: 'AI 怀疑派',
    Observer: '中立观察者',
    Neutral: '中立观察者',
  };

  return roleLabels[role] || description.slice(0, 30) || 'Neutral';
}

/**
 * Normalize status string to frontend type
 */
function normalizeStatus(status: string): 'active' | 'idle' | 'thinking' {
  const normalized = status.toLowerCase();
  if (normalized === 'active' || normalized === 'running') {
    return 'active';
  }
  if (normalized === 'thinking') {
    return 'thinking';
  }
  return 'idle';
}

/**
 * Create empty memory snapshot
 */
function createEmptyMemorySnapshot(): AgentMemorySnapshot {
  return {
    length: 0,
    content: '',
    contentSource: 'system_prompt',
    systemPrompt: {
      length: 0,
      content: '',
    },
    retrieval: {
      enabled: false,
      status: 'not_configured',
      content: '',
      items: [],
    },
  };
}
