import axios from 'axios';
import type {
  SimulationStatus,
  GenerateUsersRequest,
  GenerateUsersResponse,
  LogEntry,
  TopicListResponse,
  TopicDetail,
  TopicActivationResult,
  MetricsSummary,
  PropagationMetrics,
  PolarizationMetrics,
  HerdEffectMetrics
} from './types';

const api = axios.create({
  baseURL: '/api',  // 使用相对路径，自动适配本地开发和部署环境
  timeout: 600000,  // 10分钟超时 - 支持大规模agent的LLM调用
});

export const simulationApi = {
  updateConfig: (config: {
    platform: string;
    agentCount: number;
    maxSteps?: number;
    recsysType?: string;
  }) => api.post('/sim/config', {
    platform: config.platform,
    agent_count: config.agentCount,
    recsys_type: config.recsysType || 'twitter',
    max_steps: config.maxSteps || 50
  }),

  getStatus: () => api.get<SimulationStatus>('/sim/status'),

  step: (stepType: 'auto' | 'manual' = 'auto') => api.post('/sim/step', { step_type: stepType }),

  pause: () => api.post<SimulationStatus>('/sim/pause'),

  resume: () => api.post<SimulationStatus>('/sim/resume'),

  reset: () => api.post('/sim/reset'),

  generateUsers: (params: GenerateUsersRequest) =>
    api.post<GenerateUsersResponse>('/users/generate', params),

  sendGroupMessage: (content: string, agentName?: string) =>
    api.post('/sim/group-message', { content, agentName }),

  getLogs: () => api.get<{ logs: LogEntry[] }>('/sim/logs'),

  getTopics: () => api.get<TopicListResponse>('/topics'),

  getTopicById: (topicId: string) => api.get<TopicDetail>(`/topics/${topicId}`),

  activateTopic: (topicId: string) => api.post<TopicActivationResult>(`/topics/${topicId}/activate`),

  reloadTopics: () => api.post<{ success: boolean; message: string; topics_count: number }>('/topics/reload'),

  // Metrics APIs
  getMetricsSummary: () => api.get<MetricsSummary>('/metrics/summary'),

  getPropagationMetrics: (postId?: number) =>
    api.get<PropagationMetrics>('/metrics/propagation', { params: postId ? { post_id: postId } : {} }),

  getPolarizationMetrics: (agentIds?: string) =>
    api.get<PolarizationMetrics>('/metrics/polarization', { params: agentIds ? { agent_ids: agentIds } : {} }),

  getHerdEffectMetrics: (timeWindowSeconds?: number) =>
    api.get<HerdEffectMetrics>('/metrics/herd-effect', { params: timeWindowSeconds ? { time_window_seconds: timeWindowSeconds } : {} }),

  getMetricsHistory: (params?: {
    metric_type?: string;
    step_from?: number;
    step_to?: number;
    limit?: number;
  }) => api.get<{
    history: Array<{
      id: number;
      step_number: number;
      metric_type: string;
      metric_data: any;
      calculated_at: string;
    }>;
    total_count: number;
  }>('/metrics/history', { params }),

  getLatestMetrics: (metricType: string) =>
    api.get<any>(`/metrics/history/latest`, { params: { metric_type: metricType } }),
};
