export type ActionType = 
  | 'CREATE_POST' | 'LIKE_POST' | 'FOLLOW' | 'REPOST' | 'REPORT_POST' | 'CREATE_COMMENT';

export interface Agent {
  id: string;
  name: string;
  bio: string;
  interests: string[];
  status: 'active' | 'idle' | 'thinking';
  lastAction?: { type: ActionType; content?: string; reason: string };
  polarization?: number; // 添加极化值字段
  role?: string; // Agent 角色 (e.g., 'KOL', 'Neutral', etc.)
  influence?: number; // 影响力值
  activity?: number; // 活跃度百分比
  following?: string[]; // 关注的 agent IDs
}

export interface LogEntry {
  timestamp: string;
  agentId: string;
  actionType: ActionType;
  content: string;
  reason: string;
}



export interface SimulationStatus {
  running: boolean;
  paused: boolean;
  currentStep: number;
  currentRound?: number;     // 🆕 Current round number (10 steps = 1 round)
  activeAgents: number;
  totalPosts: number;
  polarization: number;
  agents: Agent[];
  platform?: string;
  recsys?: string;
  topics?: string[];
  regions?: string[];

  // ========== OASIS Paper Metrics ==========

  // 🆕 Information Propagation Metrics
  propagation?: {
    scale: number;           // Number of unique users in propagation
    depth: number;           // Maximum depth of propagation graph
    maxBreadth: number;      // Maximum breadth at any depth level
    round: number;           // Current round number
    nrmse?: number;          // Normalized RMSE vs real data (optional)
  };

  // 🆕 Group Polarization Metrics
  roundComparison?: {
    moreExtreme: number;     // Proportion moving to extreme positions
    moreProgressive: number; // Proportion moving to center/progressive
    unchanged: number;       // Proportion with no significant change
  };
  llmEvaluation?: string;    // LLM's explanation of polarization shift

  // 🆕 Herd Effect Metrics (Reddit Hot Score)
  herdEffect?: {
    herdEffectScore: number; // Herd effect strength (0-1)
    hotPostsCount: number;   // Number of hot posts
    coldPostsCount: number;  // Number of cold posts
    behaviorDifference: number; // Engagement difference (hot - cold) normalized
  };

  // ========== Legacy / Debug Fields ==========
  // TODO: Remove after migration is complete

  velocity?: number;        // ⚠️ DEPRECATED: Replaced by propagation.scale
  herdHhi?: number;         // ⚠️ DEPRECATED: Replaced by herdEffect.herdEffectScore

  // 🆕 Track initialization phase (Phase 4)
  initializationPhase?: boolean;
  initializationComplete?: boolean;

  // Future analytics fields
  stepTime?: number;
  opinionDistribution?: {
    farLeft: number;
    neutral: number;
    farRight: number;
  };

  // ========== Detailed Metrics (for debugging) ==========
  polarizationDetails?: any;
  propagationDetails?: any;
  herdEffectDetails?: any;
}

export interface StatsHistoryEntry extends SimulationStatus {
  timestamp: number;
}

export interface GroupMessage {
  id: string;
  timestamp: string;
  agentId: string;
  agentName: string;
  content: string;
  reason?: string;
}

export interface GenerateUsersRequest {
  platform: string;
  count: number;
  seed: number;
  topics?: string[];
  regions?: string[];
}

export interface GenerateUsersResponse {
  status: string;
  total_generated: number;
  agents: Array<{
    id: string;
    name: string;
    bio: string;
    interests: string[];
  }>;
}

export type AvailabilityStatus = 'collected' | 'not_collected' | 'unsupported' | 'failed';

export interface DatasetCounts {
  users: number;
  posts: number;
  replies: number;
  relationships: number;
  networks: number;
  topics: number;
}

export interface DatasetAvailability {
  users: AvailabilityStatus;
  posts: AvailabilityStatus;
  replies: AvailabilityStatus;
  relationships: AvailabilityStatus;
  networks: AvailabilityStatus;
  topics: AvailabilityStatus;
}

export interface PersonaDatasetSummary {
  dataset_id: string;
  label: string;
  recsys_type: string;
  source: string;
  status: 'ready' | 'partial' | 'failed';
  ingest_status: string;
  counts: DatasetCounts;
  availability: DatasetAvailability;
  latest_generation_id?: string | null;
  created_at: string;
  updated_at: string;
  meta?: Record<string, any>;
}

export interface PersonaGenerationExplanation {
  algorithm: string;
  version: string;
  real_edge_sources: string[];
  synthetic_edge_rules: Array<{
    rule: string;
    trigger: string;
    description: string;
  }>;
  feature_weights: {
    topic_overlap: number;
    description_similarity: number;
    recent_text_similarity: number;
    activity_similarity: number;
    followers_similarity: number;
  };
  persona_enrichment_mode: string;
}

export interface GeneratedAgentRecord {
  generation_id: string;
  dataset_id: string;
  algorithm: string;
  generated_agent_id: number;
  source_user_key: string;
  user_name: string;
  name: string;
  description: string;
  profile: {
    other_info: {
      user_profile: string;
      topics: string[];
      gender: string | null;
      age: number | null;
      mbti: string | null;
      country: string | null;
    };
  };
  recsys_type: string;
  user_type: string;
  interests: string[];
  metadata: Record<string, any>;
  created_at: string;
}

export interface GeneratedGraphRecord {
  generation_id: string;
  dataset_id: string;
  algorithm: string;
  nodes: Array<Record<string, any>>;
  edges: Array<Record<string, any>>;
  stats: {
    nodeCount: number;
    edgeCount: number;
    density: number;
    agentCount: number;
    topicCount: number;
    realEdgeCount: number;
    syntheticEdgeCount: number;
  };
  algorithm_explanation: PersonaGenerationExplanation;
  created_at: string;
}

export interface PersonaRawDataResponse<T = Record<string, any>> {
  dataset_id: string;
  type: string;
  stats: {
    count: number;
    page: number;
    pageSize: number;
    totalPages: number;
  };
  data: T[];
}
