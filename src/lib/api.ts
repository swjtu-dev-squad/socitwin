import axios from 'axios';
import { SimulationStatus, GenerateUsersRequest, GenerateUsersResponse, LogEntry } from './types';

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
};
