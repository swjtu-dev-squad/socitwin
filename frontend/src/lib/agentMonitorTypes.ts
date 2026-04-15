export type AgentStatus = "active" | "idle" | "thinking";
export type AgentMemoryContentSource = "system_prompt" | "retrieval";
export type AgentMemoryRetrievalStatus = "not_configured" | "ready" | "empty" | "error";

export interface AgentMemoryRetrievalItem {
  id: string;
  content: string;
  score?: number;
  source?: string;
  createdAt?: string;
}

export interface AgentMemorySnapshot {
  length: number;
  content: string;
  contentSource: AgentMemoryContentSource;
  systemPrompt: {
    length: number;
    content: string;
  };
  retrieval: {
    length: number;
    enabled: boolean;
    status: AgentMemoryRetrievalStatus;
    content: string;
    items: AgentMemoryRetrievalItem[];
  };
  debug?: {
    memoryMode?: string;
    memorySupported?: boolean;
    recentRetainedStepCount?: number;
    recentRetainedStepIds?: number[];
    compressedActionBlockCount?: number;
    compressedHeartbeatCount?: number;
    compressedRetainedStepCount?: number;
    totalRetainedStepCount?: number;
    lastObservationStage?: string;
    lastObservationPromptTokens?: number;
    lastPromptTokens?: number;
    lastRecallGate?: boolean | null;
    lastRecallQuerySource?: string;
    lastRecallQueryText?: string;
    lastRecallReasonTrace?: string;
    lastRecalledCount?: number;
    lastInjectedCount?: number;
    lastRecalledStepIds?: number[];
    lastInjectedStepIds?: number[];
    lastRuntimeFailureCategory?: string;
    lastRuntimeFailureStage?: string;
    lastPromptBudgetStatus?: string;
    lastSelectedRecentStepIds?: number[];
    lastSelectedCompressedKeys?: string[];
    lastSelectedRecallStepIds?: number[];
  };
}

export interface AgentGraphNode {
  id: string;
  name: string;
  role: string;
  roleLabel: string;
  influence: number;
  activity: number;
  status: AgentStatus;
  country?: string;
  city?: string;
}

export interface AgentGraphEdge {
  source: string;
  target: string;
  type: "follow" | "interaction";
  actionType?: string;
  weight?: number;
  active?: boolean;
}

export interface AgentOverview {
  id: string;
  name: string;
  role: string;
  roleLabel: string;
  bio: string;
  status: AgentStatus;
  influence: number;
  activity: number;
  lastAction?: {
    type: string;
    content: string;
    reason: string;
    timestamp?: string;
  } | null;
  actionContent?: string;
  country?: string;
  city?: string;
  occupation?: string;
  tags: string[];
  following: string[];
  followerCount: number;
  followingCount: number;
  interactionCount: number;
  memory: AgentMemorySnapshot;
}

export interface AgentMonitorResponse {
  simulation: {
    running: boolean;
    paused: boolean;
    currentStep: number;
    currentRound?: number | null;
    platform?: string;
    recsys?: string;
    topic?: string | null;
    polarization?: number;
    // 信息传播指标
    propagationScale?: number;      // 传播规模（参与用户数）
    propagationDepth?: number;      // 传播深度（层级数）
    propagationBreadth?: number;    // 传播广度（单层最大用户数）
    // 从众效应
    herdIndex?: number;
    memoryMode?: string;
  };
  graph: {
    nodes: AgentGraphNode[];
    edges: AgentGraphEdge[];
  };
  agents: AgentOverview[];
  updatedAt: string;
}

export interface AgentDetailResponse {
  profile: {
    id: string;
    name: string;
    user_name?: string;  // 后端返回的用户名
    bio: string;
    personaKey: string;
    personaDescription: string;
    roleLabel: string;
    gender?: string;
    age?: number;
    mbti?: string;
    country?: string;
    city?: string;
    occupation?: string;
    tags: string[];
  };
  status: {
    state: AgentStatus;
    influence: number;
    activity: number;
    followerCount: number;
    followingCount: number;
    interactionCount: number;
    polarization?: number;
    contextTokens?: number;
    retrievedMemories?: number;
    seenAgentsCount?: number;
  };
  currentViewpoint?: string;
  lastAction?: {
    type: string;
    content: string;
    reason: string;
    timestamp?: string;
  } | null;
  recentTimeline: Array<{
    timestamp: string;
    type: string;
    content: string;
    reason?: string;
  }>;
  seenPosts: Array<{
    postId: string;
    author: string;
    content: string;
    timestamp: string;
    numLikes?: number;
  }>;
  memory: AgentMemorySnapshot;
}

export interface AgentDirtyEvent {
  currentStep: number;
  updatedAt: string;
}

// ============================================================================
// Backend Response Types (from backend/app/models/simulation.py)
// ============================================================================

/**
 * Backend Agent model matching Python class Agent(BaseModel)
 * From: backend/app/models/simulation.py
 */
export interface BackendAgent {
  id: number;
  user_name: string;
  name: string;
  description: string;
  bio?: string | null;
  status: string;
  polarization: number;
  influence: number;
  activity: number;
  interests: string[];
}

/**
 * Backend SimulationStatus model matching Python class SimulationStatus(BaseModel)
 * From: backend/app/models/simulation.py
 */
export interface BackendSimulationStatus {
  state: string;
  current_step: number;
  total_steps: number;
  agent_count: number;
  platform: string;
  created_at?: string | null;
  updated_at?: string | null;
  background_task_id?: string | null;
  total_posts: number;
  total_interactions: number;
  polarization: number;
  active_agents: number;
  agents: BackendAgent[];
  metrics_summary?: any;
  error_message?: string | null;
}
