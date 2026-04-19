import type { AgentDetailResponse, AgentMonitorResponse } from './agentMonitorTypes'

async function readJson<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const message = payload?.message || payload?.error || 'Request failed'
    throw new Error(message)
  }
  return payload as T
}

export async function getAgentMonitor(): Promise<AgentMonitorResponse> {
  const response = await fetch('/api/sim/agents/monitor', {
    method: 'GET',
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
    },
  })
  return readJson<AgentMonitorResponse>(response)
}

export async function getAgentDetail(agentId: string): Promise<AgentDetailResponse> {
  const response = await fetch(`/api/sim/agents/${encodeURIComponent(agentId)}/monitor`, {
    method: 'GET',
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
    },
  })
  return readJson<AgentDetailResponse>(response)
}
