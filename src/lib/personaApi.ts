/// <reference types="vite/client" />

import type {
  GeneratedAgentRecord,
  GeneratedGraphRecord,
  PersonaDatasetSummary,
  PersonaGenerationExplanation,
  PersonaRawDataResponse,
} from "./types";

async function parseJson<T>(response: Response): Promise<T> {
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.message || payload?.error || "Request failed");
  }
  return payload as T;
}

export async function listPersonaDatasets(): Promise<{ datasets: PersonaDatasetSummary[] }> {
  const response = await fetch("/api/persona/datasets");
  return parseJson(response);
}

export async function getPersonaDataset(datasetId: string): Promise<{ dataset: PersonaDatasetSummary }> {
  const response = await fetch(`/api/persona/datasets/${datasetId}`);
  return parseJson(response);
}

export async function getPersonaRawData<T = Record<string, any>>(
  datasetId: string,
  type: string,
  page = 1,
  pageSize = 50,
): Promise<PersonaRawDataResponse<T>> {
  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  });
  const response = await fetch(`/api/persona/datasets/${datasetId}/raw/${type}?${query.toString()}`);
  return parseJson(response);
}

export async function previewTwitterFetch(params: Record<string, unknown>) {
  const response = await fetch("/api/persona/twitter/fetch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJson<{
    status: string;
    preview: {
      counts: Record<string, number>;
      availability: Record<string, string>;
      trends: string[];
      sample: {
        users: Record<string, any>[];
        posts: Record<string, any>[];
        replies: Record<string, any>[];
      };
    };
  }>(response);
}

export async function fetchAndImportTwitter(params: Record<string, unknown>) {
  const response = await fetch("/api/persona/twitter/fetch-and-import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJson<{
    status: string;
    dataset_id: string;
    dataset: PersonaDatasetSummary;
  }>(response);
}

export type GenerateDatasetArtifactsParams = {
  algorithm?: string;
  agentCount?: number;
  /** 为 true 时由 Python 子进程调用大模型批量生成模拟 users，再构建图谱（耗时较长） */
  useLlmPersonas?: boolean;
  llmBatchSize?: number;
  llmSeedSample?: number;
  llmMaxRetries?: number;
  /** 手动指定 KOL:normal 比例，形如 "1:8" */
  llmKolNormalRatio?: string;
  /** 话题节点数量（Top-K） */
  topicTopK?: number;
  /** 每个用户最多连到多少个话题 */
  topicsPerAgent?: number;
};

/** 前端等待 /generate 返回的最长时间（毫秒）；超时后 fetch 会中止，避免界面一直转圈。可在 .env 设置 VITE_PERSONA_GENERATE_TIMEOUT_MS */
const _rawTimeout = import.meta.env.VITE_PERSONA_GENERATE_TIMEOUT_MS;
const _parsedTimeout =
  _rawTimeout != null && String(_rawTimeout).trim() !== "" ? Number(_rawTimeout) : NaN;
export const PERSONA_GENERATE_FETCH_TIMEOUT_MS =
  Number.isFinite(_parsedTimeout) && _parsedTimeout > 0 ? _parsedTimeout : 1_200_000;

export async function generateDatasetArtifacts(
  datasetId: string,
  params: GenerateDatasetArtifactsParams,
) {
  const signal =
    typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function"
      ? AbortSignal.timeout(PERSONA_GENERATE_FETCH_TIMEOUT_MS)
      : undefined;
  const response = await fetch(`/api/persona/datasets/${datasetId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal,
  });
  const payload = await response.json();
  if (!response.ok) {
    const base = payload?.message || payload?.error || "Request failed";
    const stderr = typeof payload?.stderr === "string" ? payload.stderr.trim() : "";
    throw new Error(stderr ? `${base}\n\n${stderr}` : base);
  }
  return payload as {
    status: string;
    generation_id: string;
    dataset_id: string;
    graph: GeneratedGraphRecord;
    stats: GeneratedGraphRecord["stats"];
    explanation: PersonaGenerationExplanation;
    llm_meta?: Record<string, unknown>;
  };
}

export async function getGeneratedAgents(generationId: string): Promise<{
  generation_id: string;
  dataset_id: string;
  stats: { count: number };
  agents: GeneratedAgentRecord[];
}> {
  const response = await fetch(`/api/persona/generations/${generationId}/agents`);
  return parseJson(response);
}

export async function getGeneratedGraph(generationId: string): Promise<{ graph: GeneratedGraphRecord }> {
  const response = await fetch(`/api/persona/generations/${generationId}/graph`);
  return parseJson(response);
}

export async function getGenerationExplanation(generationId: string): Promise<{
  dataset_id: string;
  generation_id: string;
  explanation: PersonaGenerationExplanation;
}> {
  const response = await fetch(`/api/persona/generations/${generationId}/explanation`);
  return parseJson(response);
}
