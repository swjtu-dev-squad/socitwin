// R6 Experiment API client

export interface ExperimentFormState {
  name: string;
  datasetId: string;
  recommenders: string[];
  platform: 'REDDIT' | 'X' | 'FACEBOOK' | 'TIKTOK' | 'INSTAGRAM';
  steps: number;
  seed: number;
  agentCount: number;
}

export interface ExperimentRunResult {
  success: boolean;
  experimentId: string;
  name: string;
  datasetId: string;
  recommenders: string[];
  platform: string;
  steps: number;
  seed: number;
  runs: ExperimentRun[];
  error?: string;
}

export interface StepTrace {
  step: number;
  polarization: number;
  herd_index: number;
  velocity: number;
  total_posts: number;
  unique_active_agents: number;
}

export interface ExperimentRun {
  recommender: string;
  metrics: {
    polarization_final: number;
    herd_index_final: number;
    velocity_avg: number;
    total_posts: number;
    unique_agents?: number;
    unique_active_agents?: number;
    steps_completed?: number;
    polarization_trace?: number[];
    herd_trace?: number[];
    velocity_trace?: number[];
  };
  stepsTrace?: StepTrace[];
}

export interface ExperimentListItem {
  experimentId: string;
  name: string;
  datasetId: string;
  recommenders: string[];
  steps: number;
  seed: number;
  createdAt: string;
  summary: {
    bestPolarization?: number;
    bestVelocity?: number;
    totalPosts?: number;
  };
}

export async function runExperiment(form: ExperimentFormState): Promise<ExperimentRunResult> {
  const res = await fetch('/api/experiments/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getExperimentResult(id: string): Promise<ExperimentRunResult> {
  const res = await fetch(`/api/experiments/${encodeURIComponent(id)}/result`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function listExperiments(): Promise<ExperimentListItem[]> {
  const res = await fetch('/api/experiments');
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const data = await res.json();
  return data.experiments || [];
}
