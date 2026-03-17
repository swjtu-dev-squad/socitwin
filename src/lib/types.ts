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
  activeAgents: number;
  totalPosts: number;
  polarization: number;
  velocity?: number;        // 🆕 Information velocity (posts/second)
  herdHhi?: number;         // 🆕 Herd effect index (normalized HHI)
  agents: Agent[];
  platform?: string;
  recsys?: string;
  topics?: string[];
  regions?: string[];

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
