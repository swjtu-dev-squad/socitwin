/// <reference types="vite/client" />

import type {
  GeneratedAgentRecord,
  GeneratedGraphRecord,
  PersonaDatasetSummary,
  PersonaGenerationExplanation,
  PersonaRawDataResponse,
} from './personaTypes'

function formatHttpErrorDetail(payload: unknown, status: number): string {
  if (!payload || typeof payload !== 'object') {
    return `HTTP ${status}`
  }
  const p = payload as Record<string, unknown>
  const d = p.detail
  if (typeof d === 'string' && d.trim()) return d
  if (Array.isArray(d)) {
    return d
      .map(item =>
        typeof item === 'object' && item && 'msg' in item
          ? String((item as { msg?: string }).msg)
          : JSON.stringify(item)
      )
      .filter(Boolean)
      .join('; ')
  }
  if (d != null && typeof d !== 'object') return String(d)
  const msg = p.message ?? p.error
  if (typeof msg === 'string' && msg.trim()) return msg
  return `HTTP ${status}`
}

async function parseJson<T>(response: Response): Promise<T> {
  const raw = await response.text()
  let payload: unknown
  try {
    payload = raw ? JSON.parse(raw) : {}
  } catch {
    throw new Error(
      raw?.trim()
        ? `HTTP ${response.status}: ${raw.slice(0, 500)}`
        : `HTTP ${response.status}: 响应不是 JSON（请确认 Vite 代理 /api 指向后端 8000）`
    )
  }
  if (!response.ok) {
    throw new Error(formatHttpErrorDetail(payload, response.status))
  }
  return payload as T
}

export async function listPersonaDatasets(opts?: {
  signal?: AbortSignal
}): Promise<{ datasets: PersonaDatasetSummary[] }> {
  const response = await fetch('/api/persona/datasets', { signal: opts?.signal })
  return parseJson(response)
}

export async function getPersonaDataset(
  datasetId: string
): Promise<{ dataset: PersonaDatasetSummary }> {
  const response = await fetch(`/api/persona/datasets/${datasetId}`)
  return parseJson(response)
}

export async function getPersonaRawData<T = Record<string, any>>(
  datasetId: string,
  type: string,
  page = 1,
  pageSize = 50
): Promise<PersonaRawDataResponse<T>> {
  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
  })
  const response = await fetch(`/api/persona/datasets/${datasetId}/raw/${type}?${query.toString()}`)
  return parseJson(response)
}

export async function previewTwitterFetch(params: Record<string, unknown>) {
  const response = await fetch('/api/persona/twitter/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return parseJson<{
    status: string
    preview: {
      counts: Record<string, number>
      availability: Record<string, string>
      trends: string[]
      sample: {
        users: Record<string, any>[]
        posts: Record<string, any>[]
        replies: Record<string, any>[]
      }
    }
  }>(response)
}

export async function fetchAndImportTwitter(params: Record<string, unknown>) {
  const response = await fetch('/api/persona/twitter/fetch-and-import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return parseJson<{
    status: string
    dataset_id: string
    dataset: PersonaDatasetSummary
  }>(response)
}

export type GenerateDatasetArtifactsParams = {
  algorithm?: string
  agentCount?: number
  /** 为 true 时由 Python 子进程调用大模型批量生成模拟 users，再构建图谱（耗时较长） */
  useLlmPersonas?: boolean
  llmBatchSize?: number
  llmSeedSample?: number
  llmMaxRetries?: number
  /** 手动指定 KOL:normal 比例，形如 "1:8" */
  llmKolNormalRatio?: string
  /** 话题节点数量（Top-K） */
  topicTopK?: number
  /** 每个用户最多连到多少个话题 */
  topicsPerAgent?: number
}

/** 前端等待 /generate 返回的最长时间（毫秒）；超时后 fetch 会中止，避免界面一直转圈。可在 .env 设置 VITE_PERSONA_GENERATE_TIMEOUT_MS */
const _rawTimeout = import.meta.env.VITE_PERSONA_GENERATE_TIMEOUT_MS
const _parsedTimeout =
  _rawTimeout != null && String(_rawTimeout).trim() !== '' ? Number(_rawTimeout) : NaN
export const PERSONA_GENERATE_FETCH_TIMEOUT_MS =
  Number.isFinite(_parsedTimeout) && _parsedTimeout > 0 ? _parsedTimeout : 1_200_000

export async function generateDatasetArtifacts(
  datasetId: string,
  params: GenerateDatasetArtifactsParams
) {
  const signal =
    typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
      ? AbortSignal.timeout(PERSONA_GENERATE_FETCH_TIMEOUT_MS)
      : undefined
  const response = await fetch(`/api/persona/datasets/${datasetId}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal,
  })
  const payload = await response.json()
  if (!response.ok) {
    const base = payload?.message || payload?.error || 'Request failed'
    const stderr = typeof payload?.stderr === 'string' ? payload.stderr.trim() : ''
    throw new Error(stderr ? `${base}\n\n${stderr}` : base)
  }
  return payload as {
    status: string
    generation_id: string
    dataset_id: string
    graph: GeneratedGraphRecord
    stats: GeneratedGraphRecord['stats']
    explanation: PersonaGenerationExplanation
    llm_meta?: Record<string, unknown>
  }
}

export async function getGeneratedAgents(generationId: string): Promise<{
  generation_id: string
  dataset_id: string
  stats: { count: number }
  agents: GeneratedAgentRecord[]
}> {
  const response = await fetch(`/api/persona/generations/${generationId}/agents`)
  return parseJson(response)
}

export async function getGeneratedGraph(
  generationId: string
): Promise<{ graph: GeneratedGraphRecord }> {
  const response = await fetch(`/api/persona/generations/${generationId}/graph`)
  return parseJson(response)
}

export async function getGenerationExplanation(generationId: string): Promise<{
  dataset_id: string
  generation_id: string
  explanation: PersonaGenerationExplanation
}> {
  const response = await fetch(`/api/persona/generations/${generationId}/explanation`)
  return parseJson(response)
}

export type TwitterSqliteTopicOption = {
  topic_key: string
  topic_label: string
  last_seen_at: string | null
  post_count: number
  reply_count: number
}

export async function getTwitterSqliteTopics(params?: { minTopics?: number; recentPool?: number }) {
  const query = new URLSearchParams()
  if (params?.minTopics != null) query.set('min_topics', String(params.minTopics))
  if (params?.recentPool != null) query.set('recent_pool', String(params.recentPool))
  const suffix = query.toString()
  const response = await fetch(`/api/persona/twitter/sqlite-topics${suffix ? `?${suffix}` : ''}`)
  return parseJson<{
    status: string
    topics: TwitterSqliteTopicOption[]
    total_recent: number
    min_topics: number
  }>(response)
}

/** 按时间倒序返回近期话题全表（不随机），用于多选列表 */
export async function getTwitterSqliteTopicsList(params?: {
  recentPool?: number
  platform?: string
  signal?: AbortSignal
}) {
  const query = new URLSearchParams({ format: 'list' })
  if (params?.recentPool != null) query.set('recent_pool', String(params.recentPool))
  if (params?.platform?.trim()) query.set('platform', params.platform.trim())
  const response = await fetch(`/api/persona/twitter/sqlite-topics?${query.toString()}`, {
    signal: params?.signal,
  })
  return parseJson<{
    status: string
    topics: TwitterSqliteTopicOption[]
    total: number
    format: string
  }>(response)
}

export async function getTwitterSqliteTopicSeed(topicKey: string, userLimit = 100) {
  const query = new URLSearchParams({
    topic_key: topicKey,
    user_limit: String(userLimit),
  })
  const response = await fetch(`/api/persona/twitter/sqlite-topic-seed?${query.toString()}`)
  return parseJson<{
    status: string
    topic_key: string
    user_limit_requested: number
    users_selected: number
    kol_selected: number
    normal_selected: number
    counts: { users: number; posts: number; replies: number; topics: number }
  }>(response)
}

/** 多话题：按选中话题下帖子/评论作者合并抽样（POST，避免 URL 过长） */
export async function postTwitterSqliteTopicSeed(
  topicKeys: string[],
  seedUserCount = 100,
  platform?: string
) {
  const response = await fetch('/api/persona/twitter/sqlite-topic-seed', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic_keys: topicKeys,
      seed_user_count: seedUserCount,
      ...(platform?.trim() ? { platform: platform.trim() } : {}),
    }),
  })
  return parseJson<{
    status: string
    topic_key: string
    topic_keys: string[]
    user_limit_requested: number
    users_selected: number
    kol_selected: number
    normal_selected: number
    counts: { users: number; posts: number; replies: number; topics: number }
  }>(response)
}

export type SqlitePersistResult = {
  ok: boolean
  error?: string
  topics_upserted: number
  users_upserted: number
  user_topics_upserted: number
}

export type SqlitePersonasLlmResponse = {
  status: string
  dataset_id: string
  seed_users_built: number
  seed_sample_counts: { users: number; posts: number; replies: number; topics: number }
  users: Record<string, unknown>[]
  meta?: Record<string, unknown>
  sqlite_persist?: SqlitePersistResult
}

/** 两阶段 LLM（仿真话题 + 画像）前端等待上限，为单次画像请求的 2 倍。 */
export const PERSONA_TOPICS_PERSONAS_FETCH_TIMEOUT_MS = PERSONA_GENERATE_FETCH_TIMEOUT_MS * 2

const SOCIAL_LOCAL_PIPELINE_FETCH_MS = Number(
  import.meta.env?.VITE_SOCIAL_PIPELINE_TIMEOUT_MS || 3_600_000
)

const NEO4J_NETWORKS_SYNC_FETCH_MS = Number(
  import.meta.env?.VITE_NEO4J_NETWORKS_SYNC_TIMEOUT_MS || 300_000
)

export type SqliteTopicsPersonasLlmResponse = {
  status: string
  dataset_id: string
  seed_users_built: number
  seed_sample_counts: { users: number; posts: number; replies: number; topics: number }
  /** 与 SQLite 抽样一致，供「生成社交网络」走真实互动边 */
  seed_external_user_ids?: string[]
  topics: { title: string; summary: string }[]
  users: Record<string, unknown>[]
  meta?: Record<string, unknown>
  sqlite_persist?: SqlitePersistResult
}

/** 与旧 /api/datasets/social-graph-bundle 结构一致；基于 SQLite 真实边 + 算法补边 */
export async function postTwitterSqliteSocialGraphBundle(params: {
  topic_keys: string[]
  algorithm: string
  agents: Record<string, unknown>[]
  topics: Array<{ title: string; summary?: string }>
  seed_external_user_ids?: string[]
  seed_sample_user_count?: number
  rng_seed?: number
}) {
  const signal =
    typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
      ? AbortSignal.timeout(SOCIAL_LOCAL_PIPELINE_FETCH_MS)
      : undefined
  const response = await fetch('/api/persona/twitter/sqlite-social-graph-bundle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      topic_keys: params.topic_keys,
      algorithm: params.algorithm,
      agents: params.agents,
      topics: params.topics,
      seed_external_user_ids: params.seed_external_user_ids,
      seed_sample_user_count: params.seed_sample_user_count,
      rng_seed: params.rng_seed,
    }),
  })
  return parseJson<{
    status: string
    users: unknown
    relationships: unknown[]
    user_networks: unknown[]
    topics: Record<string, unknown> | null
    metrics: Record<string, unknown>
  }>(response)
}

/** 仿真话题 + 基于话题与种子的 LLM 用户画像（不写 Mongo） */
export async function postTwitterSqliteTopicsPersonasLlm(params: {
  topic_keys: string[]
  seed_user_count: number
  synthetic_topic_count: number
  user_target_count: number
  platform?: string
  llmBatchSize?: number
  llmSeedSample?: number
  llmMaxRetries?: number
  llmKolNormalRatio?: string
}) {
  const signal =
    typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
      ? AbortSignal.timeout(PERSONA_TOPICS_PERSONAS_FETCH_TIMEOUT_MS)
      : undefined
  const response = await fetch('/api/persona/twitter/sqlite-topics-personas-llm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic_keys: params.topic_keys,
      seed_user_count: params.seed_user_count,
      synthetic_topic_count: params.synthetic_topic_count,
      user_target_count: params.user_target_count,
      ...(params.platform?.trim() ? { platform: params.platform.trim() } : {}),
      ...(params.llmBatchSize != null ? { llmBatchSize: params.llmBatchSize } : {}),
      ...(params.llmSeedSample != null ? { llmSeedSample: params.llmSeedSample } : {}),
      ...(params.llmMaxRetries != null ? { llmMaxRetries: params.llmMaxRetries } : {}),
      ...(params.llmKolNormalRatio != null ? { llmKolNormalRatio: params.llmKolNormalRatio } : {}),
    }),
    signal,
  })
  return parseJson<SqliteTopicsPersonasLlmResponse>(response)
}

/** SQLite 种子用户 → LLM 生成画像（不写 Mongo，仅返回 users 文档数组） */
export async function postTwitterSqlitePersonasLlm(params: {
  topic_keys: string[]
  seed_user_count: number
  target_count?: number
  llmBatchSize?: number
  llmSeedSample?: number
  llmMaxRetries?: number
  llmKolNormalRatio?: string
}) {
  const signal =
    typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
      ? AbortSignal.timeout(PERSONA_GENERATE_FETCH_TIMEOUT_MS)
      : undefined
  const response = await fetch('/api/persona/twitter/sqlite-personas-llm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      topic_keys: params.topic_keys,
      seed_user_count: params.seed_user_count,
      ...(params.target_count != null ? { target_count: params.target_count } : {}),
      ...(params.llmBatchSize != null ? { llmBatchSize: params.llmBatchSize } : {}),
      ...(params.llmSeedSample != null ? { llmSeedSample: params.llmSeedSample } : {}),
      ...(params.llmMaxRetries != null ? { llmMaxRetries: params.llmMaxRetries } : {}),
      ...(params.llmKolNormalRatio != null ? { llmKolNormalRatio: params.llmKolNormalRatio } : {}),
    }),
    signal,
  })
  return parseJson<SqlitePersonasLlmResponse>(response)
}

/** 调用服务端执行 networks_neo4j.py，将 datasets/data 下 JSON 写入 Neo4j */
export async function runNetworksNeo4jSync() {
  const signal =
    typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
      ? AbortSignal.timeout(NEO4J_NETWORKS_SYNC_FETCH_MS)
      : undefined
  const response = await fetch('/api/datasets/networks-neo4j-sync', { method: 'POST', signal })
  return parseJson<{ status: string }>(response)
}

/** 依次执行 topics_classify → users_format_convert → relations_generate（datasets/data） */
export async function runSocialLocalPipeline() {
  const signal =
    typeof AbortSignal !== 'undefined' && typeof AbortSignal.timeout === 'function'
      ? AbortSignal.timeout(SOCIAL_LOCAL_PIPELINE_FETCH_MS)
      : undefined
  const response = await fetch('/api/datasets/social-local-pipeline', { method: 'POST', signal })
  return parseJson<{ status: string; metrics: Record<string, unknown> }>(response)
}

export async function getSocialGraphBundle() {
  const response = await fetch('/api/datasets/social-graph-bundle')
  return parseJson<{
    status: string
    users: unknown
    relationships: unknown[]
    user_networks: unknown[]
    topics: Record<string, unknown> | null
    metrics: Record<string, unknown>
  }>(response)
}
