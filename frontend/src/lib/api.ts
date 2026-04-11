import axios from 'axios';
import type { SimulationStatus, GenerateUsersRequest, GenerateUsersResponse, LogEntry } from './types';

const api = axios.create({
  baseURL: '/api',  // 使用相对路径，自动适配本地开发和部署环境
  timeout: 600000,  // 10分钟超时 - 支持大规模agent的LLM调用
});

export const simulationApi = {
  updateConfig: (config: {
    platform: string;
    recsys: string;
    agentCount: number;
    topics?: string[];
    regions?: string[];
    sampling_config?: {
      enabled: boolean;
      rate: number;
      strategy: string;
      min_active?: number;
      seed?: number;
    };
  }) => api.post('/sim/config', config),

  getStatus: () => api.get<SimulationStatus>('/sim/status'),

  step: () => api.post<SimulationStatus>('/sim/step'),

  pause: () => api.post<SimulationStatus>('/sim/pause'),

  resume: () => api.post<SimulationStatus>('/sim/resume'),

  reset: () => api.post('/sim/reset'),

  generateUsers: (params: GenerateUsersRequest) =>
    api.post<GenerateUsersResponse>('/users/generate', params),

  sendGroupMessage: (content: string, agentName?: string) =>
    api.post('/sim/group-message', { content, agentName }),

  getLogs: () => api.get<{ logs: LogEntry[] }>('/sim/logs'),

  getTopics: () => api.get<{ status: string; topics: Array<{ id: string; filename: string; seed_posts: string[]; agent_profiles_count: number }> }>('/topics'),

  // Analytics APIs
  getOpinionDistribution: () => api.get<{ distribution: Array<{ name: string; value: number; count: number }>; total: number }>('/analytics/opinion-distribution'),

  getHerdIndex: () => api.get<{ trend: Array<{ step: number; herdIndex: number }>; current: number }>('/analytics/herd-index'),

  // Intervention APIs
  getInterventionProfiles: () => api.get<{ status: string; intervention_profiles: Array<{
    name: string;
    description: string;
    user_name_prefix: string;
    bio: string;
    system_message: string;
    initial_posts: string[];
    comment_style: string;
  }> }>('/intervention/profiles'),

  addControlledAgentsBatch: (interventionTypes: string[], initialStep: boolean = true) =>
    api.post('/sim/intervention/batch', {
      intervention_types: interventionTypes,
      initial_step: initialStep
    }),

  listControlledAgents: () => api.get('/sim/intervention/list'),
};
