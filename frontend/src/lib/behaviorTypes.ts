/**
 * 行为控制类型定义
 *
 * 定义与行为控制系统相关的TypeScript类型和接口
 */

// ============================================================================
// 基本枚举类型
// ============================================================================

/** 行为策略类型 */
export const BehaviorStrategy = {
  LLM_AUTONOMOUS: 'llm_autonomous',
  PROBABILISTIC: 'probabilistic',
  RULE_BASED: 'rule_based',
  SCHEDULED: 'scheduled',
  MIXED: 'mixed',
} as const
export type BehaviorStrategy = (typeof BehaviorStrategy)[keyof typeof BehaviorStrategy]

/** 条件运算符 */
export const ConditionOperator = {
  EQUALS: 'equals',
  NOT_EQUALS: 'not_equals',
  GREATER_THAN: 'greater_than',
  LESS_THAN: 'less_than',
  GREATER_THAN_OR_EQUAL: 'greater_than_or_equal',
  LESS_THAN_OR_EQUAL: 'less_than_or_equal',
  CONTAINS: 'contains',
  NOT_CONTAINS: 'not_contains',
  STARTS_WITH: 'starts_with',
  ENDS_WITH: 'ends_with',
  IN: 'in',
  NOT_IN: 'not_in',
  EXISTS: 'exists',
  NOT_EXISTS: 'not_exists',
} as const
export type ConditionOperator = (typeof ConditionOperator)[keyof typeof ConditionOperator]

/** 平台类型 */
export const PlatformType = {
  TWITTER: 'twitter',
  REDDIT: 'reddit',
} as const
export type PlatformType = (typeof PlatformType)[keyof typeof PlatformType]

/** OASIS动作类型 */
export const OASISActionType = {
  CREATE_POST: 'CREATE_POST',
  CREATE_COMMENT: 'CREATE_COMMENT',
  LIKE_POST: 'LIKE_POST',
  DISLIKE_POST: 'DISLIKE_POST',
  REPOST: 'REPOST',
  QUOTE_POST: 'QUOTE_POST',
  FOLLOW: 'FOLLOW',
  REFRESH: 'REFRESH',
  DO_NOTHING: 'DO_NOTHING',
} as const
export type OASISActionType = (typeof OASISActionType)[keyof typeof OASISActionType]

// ============================================================================
// 概率分布模型
// ============================================================================

/** 动作概率 */
export interface ActionProbability {
  action_type: OASISActionType
  probability: number
  conditions?: Record<string, any>
  action_args?: Record<string, any>
  description?: string
}

/** 概率分布 */
export interface ProbabilityDistribution {
  name: string
  description?: string
  actions: ActionProbability[]
  platform?: PlatformType
}

// ============================================================================
// 规则引擎模型
// ============================================================================

/** 规则条件 */
export interface RuleCondition {
  field: string
  operator: ConditionOperator
  value?: any
}

/** 行为规则 */
export interface BehaviorRule {
  rule_id: string
  name: string
  description?: string
  priority: number
  conditions: RuleCondition[]
  action: OASISActionType
  action_args?: Record<string, any>
  enabled: boolean
}

/** 规则集 */
export interface RuleSet {
  name: string
  description?: string
  rules: BehaviorRule[]
  platform?: PlatformType
}

// ============================================================================
// 调度引擎模型
// ============================================================================

/** 时间线事件 */
export interface TimelineEvent {
  step: number
  action: OASISActionType
  action_args?: Record<string, any>
  repeat_interval?: number
  repeat_count?: number
  description?: string
}

/** 行为调度 */
export interface BehaviorSchedule {
  name: string
  description?: string
  timeline: TimelineEvent[]
  loop: boolean
}

// ============================================================================
// 混合策略模型
// ============================================================================

/** 策略权重 */
export interface StrategyWeight {
  strategy: BehaviorStrategy
  weight: number
}

/** 混合策略配置 */
export interface MixedStrategyConfig {
  name: string
  description?: string
  strategy_weights: StrategyWeight[]
  selection_mode: string
}

// ============================================================================
// 完整行为配置
// ============================================================================

/** 智能体行为配置 */
export interface AgentBehaviorConfig {
  strategy: BehaviorStrategy
  probability_distribution?: ProbabilityDistribution
  rule_set?: RuleSet
  schedule?: BehaviorSchedule
  mixed_strategy?: MixedStrategyConfig
  enabled: boolean
  platform_filter?: PlatformType
  step_range?: [number, number]
  conditions?: Record<string, any>
}

/** 行为配置模板 */
export interface BehaviorProfile {
  profile_id: string
  name: string
  description?: string
  behavior_config: AgentBehaviorConfig
  tags: string[]
  created_at: string
  updated_at: string
}

/** 行为上下文 */
export interface BehaviorContext {
  current_step: number
  platform: PlatformType
  agent_id: number
  agent_state?: Record<string, any>
  simulation_state?: Record<string, any>
  recent_actions: Array<Record<string, any>>
  environment_stats?: Record<string, any>
  timestamp: string
}

// ============================================================================
// API请求/响应模型
// ============================================================================

/** 行为配置请求 */
export interface BehaviorConfigRequest {
  agent_id: number
  behavior_config: AgentBehaviorConfig
}

/** 行为模板请求 */
export interface BehaviorProfileRequest {
  profile: BehaviorProfile
}

/** 应用模板请求 */
export interface ApplyProfileRequest {
  profile_id: string
  agent_ids: number[]
}

/** 行为配置响应 */
export interface BehaviorConfigResponse {
  success: boolean
  message: string
  agent_id?: number
  profile_id?: string
  error?: string
  timestamp: string
}

/** 行为模板列表响应 */
export interface BehaviorProfilesResponse {
  success: boolean
  profiles: BehaviorProfile[]
  count: number
  timestamp: string
}

// ============================================================================
// 统计信息模型
// ============================================================================

/** 策略统计 */
export interface StrategyStatistics {
  count: number
  percentage: number
  last_updated: string
}

/** 行为控制器状态 */
export interface BehaviorControllerStatus {
  available: boolean
  engines: {
    probabilistic: boolean
    rule: boolean
    scheduling: boolean
  }
  strategy_statistics: Record<BehaviorStrategy, StrategyStatistics>
  agent_config_count: number
  oasis_manager_connected: boolean
  timestamp: string
  error?: string
}

/** 引擎统计信息 */
export interface EngineStatistics {
  engine_type: string
  available: boolean
  statistics?: Record<string, any>
  message?: string
  timestamp: string
}

/** 预设配置选项 */
export interface PresetConfigOption {
  value: string
  label: string
  description: string
}

// ============================================================================
// 前端专用类型
// ============================================================================

/** 策略显示信息 */
export interface StrategyDisplayInfo {
  value: BehaviorStrategy
  label: string
  description: string
  color: string
  icon: string
}

/** 智能体行为配置状态 */
export interface AgentBehaviorState {
  agent_id: number
  agent_name?: string
  config?: AgentBehaviorConfig
  last_updated?: string
  strategy: BehaviorStrategy
  enabled: boolean
}

/** 行为配置表单数据 */
export interface BehaviorConfigFormData {
  agent_id?: number
  strategy: BehaviorStrategy
  probability_distribution?: Partial<ProbabilityDistribution>
  rule_set?: Partial<RuleSet>
  schedule?: Partial<BehaviorSchedule>
  mixed_strategy?: Partial<MixedStrategyConfig>
  enabled: boolean
  platform_filter?: PlatformType
  step_range?: [number, number]
  conditions?: Record<string, any>
}

// ============================================================================
// 常量定义
// ============================================================================

/** 可用策略列表 */
export const AVAILABLE_STRATEGIES: StrategyDisplayInfo[] = [
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

/** 预设配置选项 */
export const PRESET_CONFIG_OPTIONS: PresetConfigOption[] = [
  {
    value: 'default',
    label: '默认配置',
    description: 'LLM自主决策，智能体完全由AI控制',
  },
  {
    value: 'probabilistic',
    label: '概率分布',
    description: '基于概率分布选择动作，适合普通用户',
  },
  {
    value: 'rule_based',
    label: '规则引擎',
    description: '基于条件和规则触发动作，适合客服等角色',
  },
  {
    value: 'scheduled',
    label: '时间调度',
    description: '按时间线执行动作，适合营销活动',
  },
]

/** 平台选项 */
export const PLATFORM_OPTIONS = [
  { value: PlatformType.TWITTER, label: 'Twitter' },
  { value: PlatformType.REDDIT, label: 'Reddit' },
]

/** 动作类型选项 */
export const ACTION_TYPE_OPTIONS = Object.values(OASISActionType).map(value => ({
  value,
  label: value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, l => l.toUpperCase()),
}))

/** 条件运算符选项 */
export const CONDITION_OPERATOR_OPTIONS = Object.values(ConditionOperator).map(value => ({
  value,
  label: value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, l => l.toUpperCase()),
}))
