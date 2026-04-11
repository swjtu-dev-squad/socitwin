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

  // ========== Socitwin Metrics ==========

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
