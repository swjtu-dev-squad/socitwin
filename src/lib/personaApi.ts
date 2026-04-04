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

export async function generateDatasetArtifacts(datasetId: string, params: Record<string, unknown>) {
  const response = await fetch(`/api/persona/datasets/${datasetId}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJson<{
    status: string;
    generation_id: string;
    dataset_id: string;
    graph: GeneratedGraphRecord;
    stats: GeneratedGraphRecord["stats"];
    explanation: PersonaGenerationExplanation;
  }>(response);
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
