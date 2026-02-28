import axios from 'axios';
import { SimulationStatus, GenerateUsersRequest, GenerateUsersResponse } from './types';

const api = axios.create({
  baseURL: '/api',  // 使用相对路径，自动适配本地开发和部署环境
  timeout: 60000,
});

export const simulationApi = {
  updateConfig: (config: {
    platform: string;
    recsys: string;
    agentCount: number;
    speed: number;
    topics?: string[];
    regions?: string[];
  }) => api.post('/sim/config', config),

  getStatus: () => api.get<SimulationStatus>('/sim/status'),

  step: () => api.post<SimulationStatus>('/sim/step'),

  reset: () => api.post('/sim/reset'),

  generateUsers: (params: GenerateUsersRequest) =>
    api.post<GenerateUsersResponse>('/users/generate', params),

  sendGroupMessage: (content: string, agentName?: string) =>
    api.post('/sim/group-message', { content, agentName }),
};
