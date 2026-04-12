import type { AgentDetailResponse, AgentMonitorResponse } from './agentMonitorTypes';
import {
  transformToMonitorResponse,
  transformToAgentDetail,
  type BackendSimulationStatus,
} from './agentDataTransform';

async function readJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.message || payload?.error || 'Request failed';
    throw new Error(message);
  }
  return payload as T;
}

export async function getAgentMonitor(): Promise<AgentMonitorResponse> {
  // Call real backend endpoint /api/sim/status
  const response = await fetch('/api/sim/status', {
    method: 'GET',
    cache: 'no-store',
    headers: {
      'Accept': 'application/json',
    },
  });

  const backendData = await readJson<BackendSimulationStatus>(response);

  // Transform backend data to frontend format
  return transformToMonitorResponse(backendData);
}

export async function getAgentDetail(agentId: string): Promise<AgentDetailResponse> {
  // Call new backend endpoint /api/sim/agents/{agent_id}
  const response = await fetch(`/api/sim/agents/${agentId}`, {
    method: 'GET',
    cache: 'no-store',
    headers: {
      'Accept': 'application/json',
    },
  });

  const backendData = await readJson<any>(response);

  // Transform backend data to frontend format
  return transformToAgentDetail(backendData);
}
