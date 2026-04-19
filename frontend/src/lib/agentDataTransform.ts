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
} from './agentMonitorTypes'

// ============================================================================
// Backend Types (matching backend/app/models/simulation.py)
// ============================================================================

export interface BackendAgent {
  id: number
  user_name: string
  name: string
  description: string
  bio?: string
  status: string
  polarization: number
  influence: number
  activity: number
  interests: string[]
}

export interface BackendSimulationStatus {
  state: string
  current_step: number
  total_steps: number
  agent_count: number
  platform: string
  created_at?: string
  updated_at?: string
  total_posts: number
  total_interactions: number
  polarization: number
  active_agents: number
  agents: BackendAgent[]
  metrics_summary?: any
}

// ============================================================================
// Transformation Functions
// ============================================================================

/**
 * Transform backend Agent to frontend AgentOverview
 */
export function transformToAgentOverview(backendAgent: BackendAgent): AgentOverview {
  const role = deriveRoleFromDescription(backendAgent.description)
  const roleLabel = deriveRoleLabel(role, backendAgent.description)

  return {
    id: String(backendAgent.id),
    name: backendAgent.name,
    role,
    roleLabel,
    bio: backendAgent.bio || backendAgent.description || '',
    status: normalizeStatus(backendAgent.status),
    influence: backendAgent.influence,
    activity: backendAgent.activity,
    lastAction: null,
    actionContent: undefined,
    country: undefined,
    city: undefined,
    occupation: undefined,
    tags: backendAgent.interests || [],
    following: (backendAgent as any).following || [],
    followerCount: (backendAgent as any).follower_count || 0,
    followingCount: (backendAgent as any).following_count || 0,
    interactionCount: (backendAgent as any).interaction_count || 0,
    memory: createEmptyMemorySnapshot(),
  }
}

/**
 * Transform backend SimulationStatus to frontend AgentMonitorResponse
 */
export function transformToMonitorResponse(
  backendStatus: BackendSimulationStatus
): AgentMonitorResponse {
  const agents = backendStatus.agents.map(transformToAgentOverview)
  const nodes = transformToGraphNodes(agents)
  const edges = generateEdgesFromAgents(agents) // 新增：从关注关系生成边

  // 从 metrics_summary 中提取高级指标
  const metricsSummary = backendStatus.metrics_summary
  const propagationData = metricsSummary?.propagation
  const herdEffectData = metricsSummary?.herd_effect

  return {
    simulation: {
      running: backendStatus.state === 'running',
      paused: backendStatus.state === 'paused',
      currentStep: backendStatus.current_step,
      currentRound: backendStatus.current_step
        ? Math.floor(backendStatus.current_step / 10)
        : undefined,
      platform: backendStatus.platform,
      recsys: undefined,
      topic: undefined, // 后端暂无话题数据
      polarization: backendStatus.polarization,
      // 信息传播指标：包含完整的传播数据
      propagationScale: propagationData?.scale ?? 0,
      propagationDepth: propagationData?.depth ?? 0,
      propagationBreadth: propagationData?.max_breadth ?? 0,
      // 从众效应指数：从 herd_effect 的 conformity_index 中提取
      herdIndex: herdEffectData?.conformity_index ?? 0,
    },
    graph: {
      nodes,
      edges,
    },
    agents,
    updatedAt: backendStatus.updated_at || new Date().toISOString(),
  }
}

/**
 * Transform agent detail API response to frontend format
 */
export function transformToAgentDetail(backendData: any): AgentDetailResponse {
  const { profile, status, recent_actions = [], recent_posts = [] } = backendData

  // Extract role information
  const role = deriveRoleFromDescription(profile.description)
  const roleLabel = deriveRoleLabel(role, profile.description)

  // Transform recent actions to timeline
  const recentTimeline = recent_actions.map((action: any) => ({
    timestamp: action.timestamp,
    type: action.action_type,
    content: action.content,
    reason: action.reason,
  }))

  // Get last action
  const lastAction = recentTimeline.length > 0 ? recentTimeline[0] : null

  // Transform recent posts
  const seenPosts = recent_posts.map((post: any) => ({
    postId: String(post.post_id),
    author: profile.name,
    content: post.content,
    timestamp: post.created_at,
    numLikes: post.num_likes,
  }))

  return {
    profile: {
      id: String(profile.id),
      name: profile.name,
      bio: profile.bio,
      personaKey: role,
      personaDescription: profile.description,
      roleLabel,
      gender: undefined,
      age: undefined,
      mbti: undefined,
      country: undefined,
      city: undefined,
      occupation: undefined,
      tags: profile.interests || [],
    },
    status: {
      state: 'active',
      influence: status.influence,
      activity: status.activity,
      followerCount: status.follower_count || 0,
      followingCount: status.following_count || 0,
      interactionCount: status.interaction_count || 0,
      polarization: status.polarization || 0,
      contextTokens: undefined,
      retrievedMemories: undefined,
      seenAgentsCount: undefined,
    },
    currentViewpoint: undefined,
    lastAction,
    recentTimeline,
    seenPosts,
    memory: createEmptyMemorySnapshot(),
  }
}

/**
 * Transform agents to graph nodes
 */
export function transformToGraphNodes(agents: AgentOverview[]): AgentGraphNode[] {
  return agents.map(agent => ({
    id: agent.id,
    name: agent.name,
    role: agent.role,
    roleLabel: agent.roleLabel,
    influence: agent.influence,
    activity: agent.activity,
    status: agent.status,
    country: agent.country,
    city: agent.city,
  }))
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Derive agent role from description
 */
function deriveRoleFromDescription(description: string): string {
  const desc = description.toLowerCase()

  if (desc.includes('kol') || desc.includes('key opinion leader') || desc.includes('influencer')) {
    return 'KOL'
  }
  if (desc.includes('optimistic') || desc.includes('enthusiast') || desc.includes('supporter')) {
    return 'Evangelist'
  }
  if (desc.includes('skeptical') || desc.includes('critic') || desc.includes('doubter')) {
    return 'Skeptic'
  }
  if (desc.includes('neutral') || desc.includes('observer') || desc.includes('moderate')) {
    return 'Observer'
  }

  return 'Neutral'
}

/**
 * Generate graph edges from agent follow relationships
 */
function generateEdgesFromAgents(agents: AgentOverview[]): AgentGraphEdge[] {
  const edges: AgentGraphEdge[] = []

  for (const agent of agents) {
    // 从关注关系生成边
    if (agent.following && Array.isArray(agent.following)) {
      for (const targetId of agent.following) {
        edges.push({
          source: agent.id,
          target: targetId,
          type: 'follow',
        })
      }
    }
  }

  return edges
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
  }

  return roleLabels[role] || description.slice(0, 30) || 'Neutral'
}

/**
 * Normalize status string to frontend type
 */
function normalizeStatus(status: string): 'active' | 'idle' | 'thinking' {
  const normalized = status.toLowerCase()
  if (normalized === 'active' || normalized === 'running') {
    return 'active'
  }
  if (normalized === 'thinking') {
    return 'thinking'
  }
  return 'idle'
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
  }
}
