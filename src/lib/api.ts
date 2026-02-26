import axios from 'axios';
import { SimulationStatus, GenerateUsersRequest, GenerateUsersResponse } from './types';

const api = axios.create({
  baseURL: 'https://3000-ijgxvyou3aujd04xdhd8y-99d67713.us2.manus.computer/api',
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
