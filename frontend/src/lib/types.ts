export type ActionType =
  | 'CREATE_POST'
  | 'LIKE_POST'
  | 'FOLLOW'
  | 'REPOST'
  | 'REPORT_POST'
  | 'CREATE_COMMENT'

export interface Agent {
  id: string
  name: string
  bio: string
  interests: string[]
  status: 'active' | 'idle' | 'thinking'
  lastAction?: { type: ActionType; content?: string; reason: string }
  polarization?: number // 添加极化值字段
  role?: string // Agent 角色 (e.g., 'KOL', 'Neutral', etc.)
  influence?: number // 影响力值
  activity?: number // 活跃度百分比
  following?: string[] // 关注的 agent IDs
}

export interface LogEntry {
  timestamp: string
  agentId: string
  actionType: ActionType
  content: string
  reason: string
}

export interface SimulationStatus {
  // Backend state field (enum: uninitialized, configured, ready, running, paused, complete, error)
  state?: string
  originalState?: string // Keep for reference

  // Frontend compatibility fields
  running: boolean
  paused: boolean

  currentStep: number
  currentRound?: number // 🆕 Current round number (10 steps = 1 round)
  activeAgents: number
  totalPosts: number
  polarization: number
  agents: Agent[]
  platform?: string
  memoryMode?: 'upstream' | 'action_v1' | string
  contextTokenLimit?: number | null
  generationMaxTokens?: number | null
  modelBackendTokenLimit?: number | null
  errorMessage?: string | null
  recsys?: string
  topics?: string[]
  regions?: string[]

  // ========== Socitwin Metrics ==========

  // 🆕 Information Propagation Metrics
  propagation?: {
    scale: number // Number of unique users in propagation
    depth: number // Maximum depth of propagation graph
    maxBreadth: number // Maximum breadth at any depth level
    round: number // Current round number
    nrmse?: number // Normalized RMSE vs real data (optional)
  }

  // 🆕 Group Polarization Metrics
  roundComparison?: {
    moreExtreme: number // Proportion moving to extreme positions
    moreProgressive: number // Proportion moving to center/progressive
    unchanged: number // Proportion with no significant change
  }
  llmEvaluation?: string // LLM's explanation of polarization shift

  // 🆕 Herd Effect Metrics (Reddit Hot Score)
  herdEffect?: {
    herdEffectScore: number // Herd effect strength (0-1)
    hotPostsCount: number // Number of hot posts
    coldPostsCount: number // Number of cold posts
    behaviorDifference: number // Engagement difference (hot - cold) normalized
  }

  // ========== Legacy / Debug Fields ==========
  // TODO: Remove after migration is complete

  velocity?: number // ⚠️ DEPRECATED: Replaced by propagation.scale
  herdHhi?: number // ⚠️ DEPRECATED: Replaced by herdEffect.herdEffectScore

  // 🆕 Track initialization phase (Phase 4)
  initializationPhase?: boolean
  initializationComplete?: boolean

  // Future analytics fields
  stepTime?: number
  opinionDistribution?: {
    farLeft: number
    neutral: number
    farRight: number
  }

  // ========== Detailed Metrics (for debugging) ==========
  polarizationDetails?: any
  propagationDetails?: any
  herdEffectDetails?: any
}

export interface StatsHistoryEntry extends SimulationStatus {
  timestamp: number
}

export interface GroupMessage {
  id: string
  timestamp: string
  agentId: string
  agentName: string
  content: string
  reason?: string
}

export interface GenerateUsersRequest {
  platform: string
  count: number
  seed: number
  topics?: string[]
  regions?: string[]
}

export interface GenerateUsersResponse {
  status: string
  total_generated: number
  agents: Array<{
    id: string
    name: string
    bio: string
    interests: string[]
  }>
}

// ========== Topic Types (matching backend/app/models/topics.py) ==========

export interface TopicInitialPost {
  content: string
  agent_id: number
}

export interface TopicSettings {
  trigger_refresh: boolean
}

export interface Topic {
  id: string
  name: string
  description: string
  platform?: string
  topic_key?: string | null
  topic_type?: string
  trend_rank?: number | null
  post_count?: number
  reply_count?: number
  user_count?: number
  news_external_id?: string | null
  initial_post: TopicInitialPost
  settings: TopicSettings
}

export interface TopicListItem {
  id: string
  name: string
  description: string
  platform?: string
  topic_key?: string | null
  topic_type?: string
  trend_rank?: number | null
  post_count?: number
  reply_count?: number
  user_count?: number
  news_external_id?: string | null
  has_initial_post?: boolean
  settings_trigger_refresh?: boolean
}

export interface TopicListResponse {
  success: boolean
  count: number
  topics: TopicListItem[]
}

export interface TopicDetail extends Topic {
  first_seen_at?: string | null
  last_seen_at?: string | null
  available: boolean
}

export interface TopicActivationResult {
  success: boolean
  message: string
  topic_id: string
  initial_post_created?: boolean
  agents_refreshed?: number
  execution_time?: number
  error?: string
}

export interface TopicProfileSeed {
  external_user_id: string
  username?: string | null
  display_name?: string | null
  bio?: string | null
  location?: string | null
  verified: boolean
  follower_count: number
  following_count: number
  tweet_count: number
  role: string
  content_count: number
  influence_score: number
  activity_score: number
  interests: string[]
  agent_config: {
    agent_id: number
    user_name: string
    name: string
    description: string
    bio?: string | null
    profile?: Record<string, any> | null
    interests: string[]
    age?: number | null
    gender?: string | null
    mbti?: string | null
    country?: string | null
  }
}

export interface TopicProfilesResponse {
  success: boolean
  topic: TopicDetail
  count: number
  profiles: TopicProfileSeed[]
}

export interface TopicContentSeed {
  external_content_id: string
  content_type: string
  author_external_user_id?: string | null
  author_username?: string | null
  author_display_name?: string | null
  parent_external_content_id?: string | null
  root_external_content_id?: string | null
  text?: string | null
  language?: string | null
  created_at?: string | null
  like_count: number
  reply_count: number
  share_count: number
  view_count: number
  relevance_score: number
}

export interface TopicSimulationResponse {
  success: boolean
  topic: TopicDetail
  participant_count: number
  content_count: number
  profiles: TopicProfileSeed[]
  contents: TopicContentSeed[]
}

export interface ConfigResult {
  success: boolean
  message: string
  simulation_id?: string | null
  agents_created?: number
}

export interface StatusResult {
  success: boolean
  message: string
  current_state?: string
  timestamp?: string
}

// ========== Metrics Types (matching backend/app/models/metrics.py) ==========

export interface PropagationMetrics {
  scale: number
  depth: number
  max_breadth: number
  post_id?: number
  calculated_at: string
}

export interface AgentPolarization {
  agent_id: number
  agent_name: string
  direction: string
  magnitude: number
  reasoning?: string
}

export interface PolarizationMetrics {
  average_direction: string
  average_magnitude: number
  total_agents_evaluated: number
  agent_polarization?: AgentPolarization[]
  calculated_at: string
}

export interface SentimentAnalyzedPost {
  post_id: number
  user_id: number
  sentiment: '正向' | '负向' | '中性'
  confidence: number
  signed_score: number
}

export interface SentimentTendencyMetrics {
  overall_score: number
  positive_count: number
  negative_count: number
  neutral_count: number
  analyzed_post_count: number
  non_neutral_count: number
  last_post_id: number
  posts?: SentimentAnalyzedPost[]
  calculated_at: string
}

export interface HotPost {
  post_id: number
  user_id: number
  content: string
  net_score: number
  hot_score: number
  created_at: string
}

export interface HerdEffectMetrics {
  average_post_score: number
  disagree_score: number
  conformity_index: number
  hot_posts?: HotPost[]
  calculated_at: string
}

export interface MetricsSummary {
  propagation: PropagationMetrics
  polarization: PolarizationMetrics
  herd_effect: HerdEffectMetrics
  sentiment_tendency?: SentimentTendencyMetrics
  current_step: number
  timestamp: string
}

// ========== Metrics History Types (from database) ==========

export interface MetricsHistoryEntry {
  id: number
  step_number: number
  metric_type: 'propagation' | 'polarization' | 'herd_effect' | 'sentiment_tendency'
  metric_data:
    | PropagationMetrics
    | PolarizationMetrics
    | HerdEffectMetrics
    | SentimentTendencyMetrics
  calculated_at: string
}

export interface MetricsHistoryResponse {
  history: MetricsHistoryEntry[]
  total_count: number
}

// Chart data point (step-based)
export interface ChartDataPoint {
  step: number
  polarization?: number // from polarization.average_magnitude
  sentimentTendency?: number // from sentiment_tendency.overall_score
  propagation?: number // from propagation.scale
  herdEffect?: number // from herd_effect.conformity_index
}

// ========== Controlled Agent Types ==========

import { BehaviorStrategy } from './behaviorTypes'

export interface ControlledAgentConfig {
  user_name: string
  name: string
  description: string
  bio?: string
  profile?: Record<string, any>
  interests?: string[]
  behavior_strategy?: BehaviorStrategy
}

export interface AgentAddResult {
  agent_id: number
  user_name: string
  success: boolean
  error_message?: string
}

export interface AddControlledAgentsRequest {
  agents: ControlledAgentConfig[]
  check_polarization?: boolean
  polarization_threshold?: number
}

export interface AddControlledAgentsResponse {
  success: boolean
  message: string
  added_count: number
  current_polarization: number
  added_agent_ids: number[]
  results: AgentAddResult[]
}
