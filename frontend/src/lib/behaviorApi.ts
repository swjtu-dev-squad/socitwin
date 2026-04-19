/**
 * 行为控制API客户端
 *
 * 提供与后端行为控制API交互的函数
 */

import type {
  BehaviorConfigRequest,
  BehaviorConfigResponse,
  BehaviorControllerStatus,
  EngineStatistics,
  AgentBehaviorConfig,
  BehaviorStrategy,
  BehaviorProfilesResponse,
  ApplyProfileRequest,
  PresetConfigOption,
  StrategyDisplayInfo,
} from './behaviorTypes'

const API_BASE = '/api'

// ============================================================================
// 错误处理
// ============================================================================

class BehaviorApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public response?: any
  ) {
    super(message)
    this.name = 'BehaviorApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `API请求失败: ${response.status} ${response.statusText}`
    try {
      const errorData = await response.json()
      errorMessage = errorData.detail || errorData.message || errorMessage
    } catch {
      // 忽略JSON解析错误
    }
    throw new BehaviorApiError(errorMessage, response.status)
  }

  try {
    return await response.json()
  } catch (error) {
    throw new BehaviorApiError('响应JSON解析失败', response.status)
  }
}

// ============================================================================
// 智能体行为配置
// ============================================================================

/**
 * 更新智能体行为配置
 */
export async function updateAgentBehavior(
  agentId: number,
  config: AgentBehaviorConfig
): Promise<BehaviorConfigResponse> {
  const request: BehaviorConfigRequest = {
    agent_id: agentId,
    behavior_config: config,
  }

  const response = await fetch(`${API_BASE}/behavior/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  return handleResponse<BehaviorConfigResponse>(response)
}

/**
 * 获取智能体行为配置
 */
export async function getAgentBehavior(agentId: number): Promise<AgentBehaviorConfig> {
  const response = await fetch(`${API_BASE}/behavior/config/${agentId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<AgentBehaviorConfig>(response)
}

/**
 * 重置智能体行为配置为默认值
 */
export async function resetAgentBehavior(agentId: number): Promise<BehaviorConfigResponse> {
  const response = await fetch(`${API_BASE}/behavior/config/${agentId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<BehaviorConfigResponse>(response)
}

// ============================================================================
// 批量操作
// ============================================================================

/**
 * 批量更新智能体行为配置
 */
export async function batchUpdateAgentBehavior(
  requests: BehaviorConfigRequest[]
): Promise<BehaviorConfigResponse[]> {
  const response = await fetch(`${API_BASE}/behavior/config/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requests),
  })

  return handleResponse<BehaviorConfigResponse[]>(response)
}

/**
 * 应用行为配置模板到智能体
 */
export async function applyBehaviorProfile(
  profileId: string,
  agentIds: number[] = []
): Promise<BehaviorConfigResponse[]> {
  const request: ApplyProfileRequest = {
    profile_id: profileId,
    agent_ids: agentIds,
  }

  const response = await fetch(`${API_BASE}/behavior/config/apply-profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  })

  return handleResponse<BehaviorConfigResponse[]>(response)
}

// ============================================================================
// 预设配置
// ============================================================================

/**
 * 应用预定义行为配置
 */
export async function applyPresetConfig(
  agentId: number,
  preset: string,
  platform: string = 'twitter'
): Promise<BehaviorConfigResponse> {
  const params = new URLSearchParams({
    preset,
    platform,
  })

  const response = await fetch(`${API_BASE}/behavior/config/preset/${agentId}?${params}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<BehaviorConfigResponse>(response)
}

// ============================================================================
// 统计信息
// ============================================================================

/**
 * 获取行为控制器状态
 */
export async function getBehaviorControllerStatus(): Promise<BehaviorControllerStatus> {
  const response = await fetch(`${API_BASE}/behavior/status`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<BehaviorControllerStatus>(response)
}

/**
 * 获取行为控制统计信息
 */
export async function getBehaviorStatistics(): Promise<any> {
  const response = await fetch(`${API_BASE}/behavior/stats`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<any>(response)
}

/**
 * 获取概率引擎统计信息
 */
export async function getProbabilisticEngineStats(): Promise<EngineStatistics> {
  const response = await fetch(`${API_BASE}/behavior/engine/probabilistic`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<EngineStatistics>(response)
}

/**
 * 获取规则引擎统计信息
 */
export async function getRuleEngineStats(): Promise<EngineStatistics> {
  const response = await fetch(`${API_BASE}/behavior/engine/rule`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<EngineStatistics>(response)
}

/**
 * 获取调度引擎统计信息
 */
export async function getSchedulingEngineStats(): Promise<EngineStatistics> {
  const response = await fetch(`${API_BASE}/behavior/engine/scheduling`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<EngineStatistics>(response)
}

// ============================================================================
// 辅助端点
// ============================================================================

/**
 * 获取可用行为策略列表
 */
export async function getAvailableStrategies(): Promise<{
  strategies: StrategyDisplayInfo[]
}> {
  const response = await fetch(`${API_BASE}/behavior/strategies`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<{ strategies: StrategyDisplayInfo[] }>(response)
}

/**
 * 获取行为配置模板列表
 */
export async function listBehaviorProfiles(): Promise<BehaviorProfilesResponse> {
  const response = await fetch(`${API_BASE}/behavior/profiles`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<BehaviorProfilesResponse>(response)
}

/**
 * 创建行为配置模板
 */
export async function createBehaviorProfile(profile: any): Promise<BehaviorConfigResponse> {
  const response = await fetch(`${API_BASE}/behavior/profiles`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ profile }),
  })

  return handleResponse<BehaviorConfigResponse>(response)
}

/**
 * 删除行为配置模板
 */
export async function deleteBehaviorProfile(profileId: string): Promise<BehaviorConfigResponse> {
  const response = await fetch(`${API_BASE}/behavior/profiles/${profileId}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  return handleResponse<BehaviorConfigResponse>(response)
}

// ============================================================================
// 实用函数
// ============================================================================

/**
 * 获取策略显示信息
 */
export function getStrategyDisplayInfo(strategy: BehaviorStrategy): StrategyDisplayInfo {
  const strategies = [
    {
      value: BehaviorStrategy.LLM_AUTONOMOUS,
      label: 'LLM 自主决策',
      description: '原始LLM自主决策，智能体完全由AI模型控制',
      color: 'blue',
      icon: 'brain',
    },
    {
      value: BehaviorStrategy.PROBABILISTIC,
      label: '概率分布',
      description: '基于配置的概率分布选择动作',
      color: 'green',
      icon: 'dice',
    },
    {
      value: BehaviorStrategy.RULE_BASED,
      label: '规则引擎',
      description: '基于条件和规则触发动作',
      color: 'orange',
      icon: 'rules',
    },
    {
      value: BehaviorStrategy.SCHEDULED,
      label: '时间调度',
      description: '按预定义时间线执行动作',
      color: 'purple',
      icon: 'calendar',
    },
    {
      value: BehaviorStrategy.MIXED,
      label: '混合策略',
      description: '结合多种策略按权重分配',
      color: 'pink',
      icon: 'layers',
    },
  ]

  return strategies.find(s => s.value === strategy) || strategies[0]
}

/**
 * 格式化策略使用百分比
 */
export function formatStrategyPercentage(percentage: number): string {
  return `${percentage.toFixed(1)}%`
}

/**
 * 检查引擎是否可用
 */
export function isEngineAvailable(
  status: BehaviorControllerStatus,
  engine: keyof BehaviorControllerStatus['engines']
): boolean {
  return status.engines[engine]
}

// ============================================================================
// 默认配置生成
// ============================================================================

/**
 * 创建默认行为配置
 */
export function createDefaultBehaviorConfig(): AgentBehaviorConfig {
  return {
    strategy: BehaviorStrategy.LLM_AUTONOMOUS,
    enabled: true,
  }
}

/**
 * 创建概率分布配置
 */
export function createProbabilisticConfig(
  platform: 'twitter' | 'reddit' = 'twitter'
): AgentBehaviorConfig {
  const actions =
    platform === 'twitter'
      ? [
          { action_type: 'CREATE_POST' as const, probability: 0.2, description: '创建新帖子' },
          { action_type: 'LIKE_POST' as const, probability: 0.3, description: '点赞帖子' },
          { action_type: 'CREATE_COMMENT' as const, probability: 0.25, description: '评论帖子' },
          { action_type: 'REFRESH' as const, probability: 0.15, description: '刷新时间线' },
          { action_type: 'DO_NOTHING' as const, probability: 0.1, description: '休息观察' },
        ]
      : [
          { action_type: 'CREATE_POST' as const, probability: 0.15, description: '创建新帖子' },
          { action_type: 'LIKE_POST' as const, probability: 0.35, description: '点赞帖子' },
          { action_type: 'CREATE_COMMENT' as const, probability: 0.3, description: '评论帖子' },
          { action_type: 'REFRESH' as const, probability: 0.1, description: '刷新时间线' },
          { action_type: 'DISLIKE_POST' as const, probability: 0.05, description: '踩帖子' },
          { action_type: 'DO_NOTHING' as const, probability: 0.05, description: '休息观察' },
        ]

  return {
    strategy: BehaviorStrategy.PROBABILISTIC,
    probability_distribution: {
      name: 'balanced',
      description: `平衡的${platform === 'twitter' ? 'Twitter' : 'Reddit'}行为分布`,
      actions,
      platform,
    },
    enabled: true,
    platform_filter: platform,
  }
}

export default {
  updateAgentBehavior,
  getAgentBehavior,
  resetAgentBehavior,
  batchUpdateAgentBehavior,
  applyBehaviorProfile,
  applyPresetConfig,
  getBehaviorControllerStatus,
  getBehaviorStatistics,
  getProbabilisticEngineStats,
  getRuleEngineStats,
  getSchedulingEngineStats,
  getAvailableStrategies,
  listBehaviorProfiles,
  createBehaviorProfile,
  deleteBehaviorProfile,
  getStrategyDisplayInfo,
  formatStrategyPercentage,
  isEngineAvailable,
  createDefaultBehaviorConfig,
  createProbabilisticConfig,
}
