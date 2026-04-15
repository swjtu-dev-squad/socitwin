import axios from 'axios'
import type {
  SimulationStatus,
  ConfigResult,
  GenerateUsersRequest,
  GenerateUsersResponse,
  LogEntry,
  StatusResult,
  TopicListResponse,
  TopicDetail,
  TopicActivationResult,
  TopicProfilesResponse,
  TopicSimulationResponse,
  MetricsSummary,
  PropagationMetrics,
  PolarizationMetrics,
  HerdEffectMetrics,
  AddControlledAgentsRequest,
  AddControlledAgentsResponse,
  SentimentTendencyMetrics
} from './types'

const api = axios.create({
  baseURL: '/api', // 使用相对路径，自动适配本地开发和部署环境
  timeout: 600000, // 10分钟超时 - 支持大规模agent的LLM调用
})

const encodeTopicId = (topicId: string) => encodeURIComponent(topicId)

export const simulationApi = {
  updateConfig: (config: {
    platform: string
    agentCount: number
    maxSteps?: number
    recsysType?: string
    memoryMode?: 'upstream' | 'action_v1'
    contextTokenLimit?: number
    maxTokens?: number
    agentSource?: {
      sourceType: 'template' | 'file' | 'manual'
      templateName?: string
      filePath?: string
      manualConfig?: Record<string, any>[]
    }
  }) =>
    api.post<ConfigResult>('/sim/config', {
      platform: config.platform,
      agent_count: config.agentCount,
      recsys_type: config.recsysType || config.platform,
      memory_mode: config.memoryMode,
      max_steps: config.maxSteps || 50,
      context_token_limit: config.contextTokenLimit,
      llm_config: config.maxTokens ? { max_tokens: config.maxTokens } : undefined,
      ...(config.agentSource
        ? {
            agent_source: {
              source_type: config.agentSource.sourceType,
              template_name: config.agentSource.templateName,
              file_path: config.agentSource.filePath,
              manual_config: config.agentSource.manualConfig,
            },
          }
        : {}),
    }),

  getStatus: () => api.get<SimulationStatus>('/sim/status'),

  step: (stepType: 'auto' | 'manual' = 'auto') => api.post('/sim/step', { step_type: stepType }),

  pause: () => api.post<SimulationStatus>('/sim/pause'),

  resume: () => api.post<SimulationStatus>('/sim/resume'),

  reset: () => api.post<StatusResult>('/sim/reset'),

  generateUsers: (params: GenerateUsersRequest) =>
    api.post<GenerateUsersResponse>('/users/generate', params),

  sendGroupMessage: (content: string, agentName?: string) =>
    api.post('/sim/group-message', { content, agentName }),

  getLogs: () => api.get<{ logs: LogEntry[] }>('/sim/logs'),

  getTopics: (params?: { platform?: string; limit?: number }) =>
    api.get<TopicListResponse>('/topics', { params }),

  getTopicById: (topicId: string) => api.get<TopicDetail>(`/topics/${encodeTopicId(topicId)}`),

  getTopicProfiles: (topicId: string, params?: { platform?: string; limit?: number }) =>
    api.get<TopicProfilesResponse>(`/topics/${encodeTopicId(topicId)}/profiles`, { params }),

  getTopicSimulation: (
    topicId: string,
    params?: { platform?: string; participant_limit?: number; content_limit?: number }
  ) => api.get<TopicSimulationResponse>(`/topics/${encodeTopicId(topicId)}/simulation`, { params }),

  activateTopic: (topicId: string, params?: { platform?: string }) =>
    api.post<TopicActivationResult>(`/topics/${encodeTopicId(topicId)}/activate`, undefined, {
      params,
    }),

  reloadTopics: (params?: { platform?: string }) =>
    api.post<{ success: boolean; message: string; topics_loaded: number }>(
      '/topics/reload',
      undefined,
      { params }
    ),

  // Metrics APIs
  getMetricsSummary: () => api.get<MetricsSummary>('/metrics/summary'),

  getPropagationMetrics: (postId?: number) =>
    api.get<PropagationMetrics>('/metrics/propagation', {
      params: postId ? { post_id: postId } : {},
    }),

  getPolarizationMetrics: (agentIds?: string) =>
    api.get<PolarizationMetrics>('/metrics/polarization', {
      params: agentIds ? { agent_ids: agentIds } : {},
    }),

  getHerdEffectMetrics: (timeWindowSeconds?: number) =>
    api.get<HerdEffectMetrics>('/metrics/herd-effect', {
      params: timeWindowSeconds ? { time_window_seconds: timeWindowSeconds } : {},
    }),

  getSentimentTendencyMetrics: () =>
    api.get<SentimentTendencyMetrics>('/metrics/sentiment-tendency'),

  getMetricsHistory: (params?: {
    metric_type?: string
    step_from?: number
    step_to?: number
    limit?: number
  }) =>
    api.get<{
      history: Array<{
        id: number
        step_number: number
        metric_type: string
        metric_data: any
        calculated_at: string
      }>
      total_count: number
    }>('/metrics/history', { params }),

  getLatestMetrics: (metricType: string) =>
    api.get<any>(`/metrics/history/latest`, { params: { metric_type: metricType } }),

  // Controlled Agents APIs
  addControlledAgents: (request: AddControlledAgentsRequest) =>
    api.post<AddControlledAgentsResponse>('/sim/agents/controlled', request),
}
