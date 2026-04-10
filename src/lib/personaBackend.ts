import { spawn } from "child_process";
import { createHash, randomUUID } from "crypto";
import { existsSync } from "fs";
import path from "path";
import type { Db } from "mongodb";
import { COLLECTIONS, type ImportType } from "./mongodb";

export const PERSONA_RAW_TYPES = [
  "users",
  "posts",
  "replies",
  "relationships",
  "networks",
  "topics",
] as const;

export type PersonaRawType = (typeof PERSONA_RAW_TYPES)[number];
export type AvailabilityStatus = "collected" | "not_collected" | "unsupported" | "failed";

export interface DatasetCounts {
  users: number;
  posts: number;
  replies: number;
  relationships: number;
  networks: number;
  topics: number;
}

export interface DatasetAvailability {
  users: AvailabilityStatus;
  posts: AvailabilityStatus;
  replies: AvailabilityStatus;
  relationships: AvailabilityStatus;
  networks: AvailabilityStatus;
  topics: AvailabilityStatus;
}

export interface PersonaDatasetManifest {
  dataset_id: string;
  label: string;
  recsys_type: string;
  source: string;
  status: "ready" | "partial" | "failed";
  ingest_status: string;
  counts: DatasetCounts;
  availability: DatasetAvailability;
  latest_generation_id?: string | null;
  created_at: string;
  updated_at: string;
  meta?: Record<string, unknown>;
}

export interface TwitterFetchPreview {
  payload: Record<string, any>;
  counts: DatasetCounts;
  availability: DatasetAvailability;
}

const ZERO_COUNTS: DatasetCounts = {
  users: 0,
  posts: 0,
  replies: 0,
  relationships: 0,
  networks: 0,
  topics: 0,
};

const EMPTY_AVAILABILITY: DatasetAvailability = {
  users: "not_collected",
  posts: "not_collected",
  replies: "not_collected",
  relationships: "not_collected",
  networks: "not_collected",
  topics: "not_collected",
};

export class PersonaProcessError extends Error {
  statusCode: number;
  stderr?: string;
  stdoutPreview?: string;
  errorType?: string;

  constructor(
    message: string,
    options?: { statusCode?: number; stderr?: string; stdoutPreview?: string; errorType?: string },
  ) {
    super(message);
    this.name = "PersonaProcessError";
    this.statusCode = options?.statusCode ?? 500;
    this.stderr = options?.stderr;
    this.stdoutPreview = options?.stdoutPreview;
    this.errorType = options?.errorType;
  }
}

function nowIso(): string {
  return new Date().toISOString();
}

function asArray<T>(value: T[] | undefined | null): T[] {
  return Array.isArray(value) ? value : [];
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function normalizeString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function uniqueStrings(values: unknown[]): string[] {
  return Array.from(
    new Set(
      values
        .map((value) => normalizeString(value))
        .filter(Boolean),
    ),
  );
}

function collectionNameFromType(type: PersonaRawType): string {
  const mapping: Record<PersonaRawType, string> = {
    users: COLLECTIONS.USERS,
    posts: COLLECTIONS.POSTS,
    replies: COLLECTIONS.REPLIES,
    relationships: COLLECTIONS.RELATIONSHIPS,
    networks: COLLECTIONS.NETWORKS,
    topics: COLLECTIONS.TOPICS,
  };
  return mapping[type];
}

function formatTimestampForId(date = new Date()): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  const hours = String(date.getUTCHours()).padStart(2, "0");
  const minutes = String(date.getUTCMinutes()).padStart(2, "0");
  const seconds = String(date.getUTCSeconds()).padStart(2, "0");
  return `${year}${month}${day}T${hours}${minutes}${seconds}Z`;
}

export function createDatasetId(): string {
  return `dataset_${formatTimestampForId()}_${randomUUID().slice(0, 8)}`;
}

export function createGenerationId(): string {
  return `generation_${randomUUID()}`;
}

export function emptyCounts(): DatasetCounts {
  return { ...ZERO_COUNTS };
}

export function emptyAvailability(): DatasetAvailability {
  return { ...EMPTY_AVAILABILITY };
}

export function ensureCounts(partial?: Partial<DatasetCounts>): DatasetCounts {
  return {
    users: partial?.users ?? 0,
    posts: partial?.posts ?? 0,
    replies: partial?.replies ?? 0,
    relationships: partial?.relationships ?? 0,
    networks: partial?.networks ?? 0,
    topics: partial?.topics ?? 0,
  };
}

export function determineDatasetStatus(availability: DatasetAvailability): "ready" | "partial" | "failed" {
  const values = Object.values(availability);
  if (values.every((value) => value === "failed")) return "failed";
  const requiredOk =
    (availability.users === "collected" || availability.users === "unsupported") &&
    (availability.posts === "collected" || availability.posts === "unsupported");
  if (requiredOk) return "ready";
  return "partial";
}

function buildExternalId(type: PersonaRawType, doc: Record<string, any>, recsysType: string): string {
  if (type === "users") {
    return (
      normalizeString(doc.twitter_user_id) ||
      normalizeString(doc.external_user_id) ||
      normalizeString(doc.external_id) ||
      normalizeString(doc.user_name) ||
      `${recsysType}:user:${doc.agent_id ?? randomUUID()}`
    );
  }
  if (type === "posts") {
    return (
      normalizeString(doc.twitter_post_id) ||
      normalizeString(doc.external_post_id) ||
      normalizeString(doc.external_id) ||
      `${recsysType}:post:${doc.post_id ?? randomUUID()}`
    );
  }
  if (type === "replies") {
    return (
      normalizeString(doc.twitter_reply_id) ||
      normalizeString(doc.external_reply_id) ||
      normalizeString(doc.external_id) ||
      `${recsysType}:reply:${doc.reply_id ?? randomUUID()}`
    );
  }
  if (type === "relationships") {
    return normalizeString(doc.id) || normalizeString(doc.external_id) || `${recsysType}:relationship:${randomUUID()}`;
  }
  if (type === "networks") {
    return normalizeString(doc.userId) || normalizeString(doc.external_id) || `${recsysType}:network:${randomUUID()}`;
  }
  return normalizeString(doc.category) || normalizeString(doc.external_id) || `${recsysType}:topic:${randomUUID()}`;
}

function stableSignature(type: PersonaRawType, doc: Record<string, any>, recsysType: string): string {
  const stable = buildExternalId(type, doc, recsysType);
  return createHash("sha1").update(`${type}:${stable}`).digest("hex");
}

function annotateRawDoc(params: {
  type: PersonaRawType;
  doc: Record<string, any>;
  datasetId: string;
  recsysType: string;
  source: string;
  ingestStatus: string;
}): Record<string, any> {
  const { type, doc, datasetId, recsysType, source, ingestStatus } = params;
  return {
    ...doc,
    recsys_type: normalizeString(doc.recsys_type) || recsysType,
    dataset_id: datasetId,
    source,
    ingest_status: ingestStatus,
    external_id: buildExternalId(type, doc, recsysType),
    stable_signature: stableSignature(type, doc, recsysType),
  };
}

export function normalizeImportDocs(params: {
  type: ImportType;
  data: any;
  datasetId: string;
  recsysType: string;
  source: string;
  ingestStatus?: string;
}): Record<string, any>[] {
  const { type, data, datasetId, recsysType, source, ingestStatus = "imported" } = params;
  if (type === "topics") {
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return [];
    }
    return Object.entries(data).map(([category, topics]) =>
      annotateRawDoc({
        type: "topics",
        doc: {
          recsys_type: recsysType,
          category,
          topics: Array.isArray(topics) ? topics : [],
        },
        datasetId,
        recsysType,
        source,
        ingestStatus,
      }),
    );
  }

  const docs = Array.isArray(data) ? data : [data];
  return docs.map((doc) =>
    annotateRawDoc({
      type,
      doc: doc && typeof doc === "object" ? doc : {},
      datasetId,
      recsysType,
      source,
      ingestStatus,
    }),
  );
}

export function summarizeCountsFromDocs(type: PersonaRawType, docs: Record<string, any>[]): DatasetCounts {
  const counts = emptyCounts();
  counts[type] = docs.length;
  return counts;
}

export function buildAvailability(counts: Partial<DatasetCounts>, overrides?: Partial<DatasetAvailability>): DatasetAvailability {
  const normalizedCounts = ensureCounts(counts);
  const availability = emptyAvailability();
  for (const type of PERSONA_RAW_TYPES) {
    availability[type] = normalizedCounts[type] > 0 ? "collected" : "not_collected";
  }
  return { ...availability, ...overrides };
}

export async function ensurePersonaIndexes(db: Db): Promise<void> {
  const commonOptions = { background: true } as const;
  await Promise.all([
    db.collection(COLLECTIONS.USERS).createIndex({ dataset_id: 1, external_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.POSTS).createIndex({ dataset_id: 1, external_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.REPLIES).createIndex({ dataset_id: 1, external_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.RELATIONSHIPS).createIndex({ dataset_id: 1, external_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.NETWORKS).createIndex({ dataset_id: 1, external_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.TOPICS).createIndex({ dataset_id: 1, external_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.PERSONA_DATASETS).createIndex({ dataset_id: 1 }, { ...commonOptions, unique: true }),
    db.collection(COLLECTIONS.PERSONA_DATASETS).createIndex({ recsys_type: 1, updated_at: -1 }, commonOptions),
    db.collection(COLLECTIONS.GENERATED_AGENTS).createIndex({ generation_id: 1, generated_agent_id: 1 }, commonOptions),
    db.collection(COLLECTIONS.GENERATED_GRAPHS).createIndex({ generation_id: 1 }, { ...commonOptions, unique: true }),
  ]);
}

export async function getDatasetManifest(db: Db, datasetId: string): Promise<PersonaDatasetManifest | null> {
  const manifest = await db.collection<PersonaDatasetManifest>(COLLECTIONS.PERSONA_DATASETS).findOne(
    { dataset_id: datasetId },
    { projection: { _id: 0 } },
  );
  return manifest;
}

export async function upsertDatasetManifest(
  db: Db,
  patch: Omit<PersonaDatasetManifest, "created_at" | "updated_at" | "status"> & {
    created_at?: string;
    updated_at?: string;
    status?: PersonaDatasetManifest["status"];
  },
): Promise<PersonaDatasetManifest> {
  const createdAt = patch.created_at || nowIso();
  const updatedAt = patch.updated_at || nowIso();
  const availability = patch.availability;
  const manifest: PersonaDatasetManifest = {
    dataset_id: patch.dataset_id,
    label: patch.label,
    recsys_type: patch.recsys_type,
    source: patch.source,
    ingest_status: patch.ingest_status,
    counts: ensureCounts(patch.counts),
    availability,
    latest_generation_id: patch.latest_generation_id ?? null,
    created_at: createdAt,
    updated_at: updatedAt,
    status: patch.status || determineDatasetStatus(availability),
    meta: patch.meta ?? {},
  };
  const { created_at: _ignoredCreatedAt, ...manifestWithoutCreatedAt } = manifest;

  await db.collection(COLLECTIONS.PERSONA_DATASETS).updateOne(
    { dataset_id: manifest.dataset_id },
    {
      $set: {
        ...manifestWithoutCreatedAt,
        updated_at: updatedAt,
      },
      $setOnInsert: {
        created_at: createdAt,
      },
    },
    { upsert: true },
  );

  return manifest;
}

export async function countDocsByDataset(db: Db, datasetId: string): Promise<DatasetCounts> {
  const counts = await Promise.all(
    PERSONA_RAW_TYPES.map((type) =>
      db.collection(collectionNameFromType(type)).countDocuments({ dataset_id: datasetId }),
    ),
  );

  return {
    users: counts[0],
    posts: counts[1],
    replies: counts[2],
    relationships: counts[3],
    networks: counts[4],
    topics: counts[5],
  };
}

export async function loadDatasetRawData(db: Db, datasetId: string): Promise<Record<PersonaRawType, Record<string, any>[]>> {
  const rawData = PERSONA_RAW_TYPES.reduce(
    (acc, type) => {
      acc[type] = [];
      return acc;
    },
    {} as Record<PersonaRawType, Record<string, any>[]>,
  );

  const entries = await Promise.all(
    PERSONA_RAW_TYPES.map(async (type) => {
      const docs = await db
        .collection(collectionNameFromType(type))
        .find({ dataset_id: datasetId }, { projection: { _id: 0 } })
        .toArray();
      return [type, docs] as const;
    }),
  );

  for (const [type, docs] of entries) {
    rawData[type] = docs as Record<string, any>[];
  }

  return rawData;
}

export function normalizeTwitterFetchPreview(payload: Record<string, any>): TwitterFetchPreview {
  const users = asArray(payload.users);
  const posts = asArray(payload.posts);
  const replies = asArray(payload.replies);
  const topicsSource =
    payload.topics_document && typeof payload.topics_document === "object"
      ? payload.topics_document
      : Array.isArray(payload.topics)
        ? { twitter_trends: payload.topics }
        : {};
  const topics = Object.entries(topicsSource).map(([category, value]) => ({
    category,
    topics: Array.isArray(value) ? value : [],
  }));

  const counts = ensureCounts({
    users: users.length,
    posts: posts.length,
    replies: replies.length,
    topics: topics.length,
  });
  const availability = buildAvailability(counts, {
    relationships: "not_collected",
    networks: "unsupported",
  });

  return {
    payload: {
      ...payload,
      users,
      posts,
      replies,
      topics_document: topicsSource,
    },
    counts,
    availability,
  };
}

export function normalizeTwitterFetchForDataset(params: {
  datasetId: string;
  payload: Record<string, any>;
  source?: string;
}): {
  docs: Record<PersonaRawType, Record<string, any>[]>;
  counts: DatasetCounts;
  availability: DatasetAvailability;
} {
  const { datasetId, payload, source = "twitter_live_fetch" } = params;
  const preview = normalizeTwitterFetchPreview(payload);
  const recsysType = "twitter";

  const users = preview.payload.users.map((doc: Record<string, any>) =>
    annotateRawDoc({
      type: "users",
      doc,
      datasetId,
      recsysType,
      source,
      ingestStatus: "collected",
    }),
  );

  const posts = preview.payload.posts.map((doc: Record<string, any>) =>
    annotateRawDoc({
      type: "posts",
      doc,
      datasetId,
      recsysType,
      source,
      ingestStatus: "collected",
    }),
  );

  const replies = preview.payload.replies.map((doc: Record<string, any>) =>
    annotateRawDoc({
      type: "replies",
      doc,
      datasetId,
      recsysType,
      source,
      ingestStatus: "collected",
    }),
  );

  const topicsSource = preview.payload.topics_document || {};
  const topics = Object.entries(topicsSource).map(([category, topicsValue]) =>
    annotateRawDoc({
      type: "topics",
      doc: {
        category,
        topics: Array.isArray(topicsValue) ? topicsValue : [],
      },
      datasetId,
      recsysType,
      source,
      ingestStatus: "collected",
    }),
  );

  return {
    docs: {
      users,
      posts,
      replies,
      relationships: [],
      networks: [],
      topics,
    },
    counts: preview.counts,
    availability: preview.availability,
  };
}

export async function insertDatasetDocs(
  db: Db,
  docsByType: Record<PersonaRawType, Record<string, any>[]>,
): Promise<void> {
  await Promise.all(
    PERSONA_RAW_TYPES.map(async (type) => {
      const docs = docsByType[type];
      if (!docs.length) return;
      await db.collection(collectionNameFromType(type)).insertMany(docs, { ordered: false });
    }),
  );
}

export async function runTwitterFetchProcess(
  repoRoot: string,
  rawOptions: Record<string, unknown>,
): Promise<Record<string, any>> {
  const pythonBin = path.join(repoRoot, ".venv", "bin", "python");
  const scriptPath = path.join(repoRoot, "oasis_dashboard", "datasets", "fetch_twitter_data.py");

  if (!existsSync(pythonBin)) {
    throw new PersonaProcessError("未找到 .venv/bin/python，请先执行: uv sync", { statusCode: 500 });
  }
  if (!existsSync(scriptPath)) {
    throw new PersonaProcessError("未找到 oasis_dashboard/datasets/fetch_twitter_data.py", { statusCode: 404 });
  }

  const args = [scriptPath, "--preview"];
  const maxTrends = rawOptions.maxTrends ?? rawOptions.max_trends;
  const maxPosts = rawOptions.maxPosts ?? rawOptions.max_posts;
  const maxRepliesPerPost = rawOptions.maxRepliesPerPost ?? rawOptions.max_replies_per_post;

  if (maxTrends != null) {
    args.push("--max-trends", String(Number(maxTrends)));
  }
  if (maxPosts != null) {
    args.push("--max-posts", String(Number(maxPosts)));
  }
  if (maxRepliesPerPost != null) {
    args.push("--max-replies-per-post", String(Number(maxRepliesPerPost)));
  }

  const payload = await new Promise<Record<string, any>>((resolve, reject) => {
    const child = spawn(pythonBin, args, {
      cwd: repoRoot,
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";
    const timeoutMs = 600_000;
    const killTimer = setTimeout(() => {
      child.kill("SIGTERM");
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(killTimer);
      reject(new PersonaProcessError(error.message, { stderr }));
    });
    child.on("close", (code) => {
      clearTimeout(killTimer);
      const trimmed = stdout.trim();
      if (code !== 0) {
        try {
          const parsed = JSON.parse(trimmed) as { error?: string; status_code?: number; type?: string };
          if (parsed?.error) {
            reject(
              new PersonaProcessError(parsed.error, {
                statusCode:
                  typeof parsed.status_code === "number" && parsed.status_code >= 400 && parsed.status_code < 600
                    ? parsed.status_code
                    : 502,
                stderr: stderr.slice(-4000),
                errorType: parsed.type,
              }),
            );
            return;
          }
        } catch {
          // Ignore parse errors and fall through to generic message.
        }
        reject(
          new PersonaProcessError(`Python 进程退出码 ${code}`, {
            stderr: stderr.slice(-4000),
            stdoutPreview: trimmed.slice(0, 1000),
          }),
        );
        return;
      }

      try {
        const parsed = JSON.parse(trimmed) as Record<string, any>;
        if (parsed?.error) {
          reject(
            new PersonaProcessError(String(parsed.error), {
              stderr: stderr.slice(-4000),
              errorType: typeof parsed.type === "string" ? parsed.type : undefined,
            }),
          );
          return;
        }
        resolve(parsed);
      } catch {
        reject(
          new PersonaProcessError("无法解析 Python 输出的 JSON", {
            stderr: stderr.slice(-4000),
            stdoutPreview: trimmed.slice(0, 1000),
          }),
        );
      }
    });
  });

  return payload;
}

export interface LlmPersonaWorkerPayload {
  seed_users: Record<string, unknown>[];
  target_count: number;
  dataset_id: string;
  recsys_type: string;
  batch_size?: number;
  seed_sample?: number;
  max_retries?: number;
  kol_normal_ratio?: string;
}

/** 从 stdout 中取最后一行可解析的 JSON 对象（兼容依赖库往 stdout 打日志的情况） */
function parseLastJsonObjectFromStdout(raw: string): Record<string, unknown> {
  const lines = raw.split(/\n/).map((l) => l.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i];
    if (!line.startsWith("{") && !line.startsWith("[")) continue;
    try {
      const parsed = JSON.parse(line) as Record<string, unknown>;
      if (parsed && typeof parsed === "object") return parsed;
    } catch {
      continue;
    }
  }
  throw new SyntaxError("stdout 中未找到合法 JSON 对象");
}

function buildLlmWorkerIoHint(stderrTail: string, stdoutRaw: string): string {
  const parts: string[] = [];
  const st = stderrTail.trim();
  const so = stdoutRaw.trim();
  if (st) parts.push(`Python stderr（节选）:\n${stderrTail.slice(-2500)}`);
  if (so) parts.push(`Python stdout（节选）:\n${so.trim().slice(0, 2000)}`);
  if (!parts.length) {
    return (
      "（子进程几乎无输出：常见于达到 OASIS_LLM_PERSONA_TIMEOUT_MS 被 SIGTERM 结束、OOM(SIGKILL)、或进程在写出 JSON 前崩溃。可增大超时、减小生成数量或 llmBatchSize。）"
    );
  }
  return parts.join("\n\n");
}

function describeLlmWorkerExit(
  code: number | null,
  signal: NodeJS.Signals | null,
  timeoutMs: number,
): string {
  if (signal) {
    return `Python 子进程被信号终止（${signal}）。常见原因：超时（OASIS_LLM_PERSONA_TIMEOUT_MS=${timeoutMs}ms）、内存不足(OOM) 或外部杀进程。`;
  }
  if (code === null) {
    return `Python 子进程异常结束（退出码为空，可能被信号终止但未上报 signal）。当前超时配置: ${timeoutMs}ms。`;
  }
  return `Python 进程退出码 ${code}`;
}

/**
 * 调用 Python `oasis_dashboard.persona_llm_worker`：根据种子用户批量 LLM 生成 raw.users 形态文档。
 * 日志应在 stderr；若第三方库污染 stdout，会尝试解析最后一行 JSON。
 */
export async function runLlmPersonaWorker(
  repoRoot: string,
  payload: LlmPersonaWorkerPayload,
): Promise<{ status: string; users: Record<string, any>[]; meta?: Record<string, unknown>; error?: string }> {
  const pythonBin = path.join(repoRoot, ".venv", "bin", "python");
  if (!existsSync(pythonBin)) {
    throw new PersonaProcessError("未找到 .venv/bin/python，请先执行: uv sync", { statusCode: 500 });
  }

  const timeoutMs = Number(process.env.OASIS_LLM_PERSONA_TIMEOUT_MS || 900_000);

  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, ["-m", "oasis_dashboard.persona_llm_worker"], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    let stdout = "";
    let stderr = "";
    const killTimer = setTimeout(() => {
      child.kill("SIGTERM");
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(killTimer);
      reject(new PersonaProcessError(error.message, { stderr }));
    });
    child.on("close", (code, signal) => {
      clearTimeout(killTimer);
      const stderrTail = stderr.slice(-8000);
      let parsed: {
        status?: string;
        users?: Record<string, any>[];
        meta?: Record<string, unknown>;
        error?: string;
        type?: string;
      };
      try {
        parsed = parseLastJsonObjectFromStdout(stdout) as typeof parsed;
      } catch {
        const exitDesc = describeLlmWorkerExit(code, signal, timeoutMs);
        const hint = buildLlmWorkerIoHint(stderrTail, stdout);
        reject(
          new PersonaProcessError(
            code === 0 && !signal
              ? `无法解析 Python 输出的 JSON。\n${hint}`
              : `${exitDesc}\n且无法解析最后一行 JSON。\n${hint}`,
            {
              statusCode: 502,
              stderr: stderrTail,
              stdoutPreview: stdout.trim().slice(0, 2000),
            },
          ),
        );
        return;
      }

      if (parsed?.status === "error" || parsed?.error) {
        reject(
          new PersonaProcessError(
            `${String(parsed.error || "LLM 用户生成失败")}${stderrTail ? `\n${stderrTail.slice(-2000)}` : ""}`,
            {
              statusCode: 502,
              stderr: stderrTail,
              errorType: typeof parsed.type === "string" ? parsed.type : undefined,
            },
          ),
        );
        return;
      }
      if (code !== 0 || signal) {
        const exitDesc = describeLlmWorkerExit(code, signal, timeoutMs);
        reject(
          new PersonaProcessError(
            `${exitDesc}${stderrTail ? `\n${stderrTail.slice(-2500)}` : ""}`,
            {
              stderr: stderrTail,
              stdoutPreview: stdout.trim().slice(0, 2000),
            },
          ),
        );
        return;
      }
      if (!Array.isArray(parsed.users) || parsed.users.length === 0) {
        reject(
          new PersonaProcessError("LLM 未返回任何用户", {
            stderr: stderrTail,
            stdoutPreview: stdout.trim().slice(0, 2000),
          }),
        );
        return;
      }
      resolve({
        status: parsed.status || "ok",
        users: parsed.users,
        meta: parsed.meta,
      });
    });

    const input = JSON.stringify(payload);
    child.stdin.write(input, "utf8");
    child.stdin.end();
  });
}

export interface Neo4jImportWorkerPayload {
  generation_id: string;
  dataset_id: string;
  agents: Record<string, any>[];
  graph: Record<string, any>;
}

/**
 * 调用 Python `oasis_dashboard.neo4j_import_worker`：将生成的 agents + graph 实时写入 Neo4j。
 * - 依赖通过 uv 安装（pyproject.toml 已包含 neo4j / neo4j-driver）
 * - 通过环境变量 NEO4J_URI/NEO4J_PASSWORD 配置连接
 */
export async function runNeo4jImportWorker(
  repoRoot: string,
  payload: Neo4jImportWorkerPayload,
): Promise<{ status: string; counts?: Record<string, number>; error?: string; type?: string }> {
  const pythonBin = path.join(repoRoot, ".venv", "bin", "python");
  if (!existsSync(pythonBin)) {
    throw new PersonaProcessError("未找到 .venv/bin/python，请先执行: uv sync", { statusCode: 500 });
  }

  const timeoutMs = Number(process.env.OASIS_NEO4J_IMPORT_TIMEOUT_MS || 120_000);

  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, ["-m", "oasis_dashboard.neo4j_import_worker"], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    let stdout = "";
    let stderr = "";
    const killTimer = setTimeout(() => {
      child.kill("SIGTERM");
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(killTimer);
      reject(new PersonaProcessError(error.message, { stderr: stderr.slice(-4000) }));
    });
    child.on("close", (code, signal) => {
      clearTimeout(killTimer);
      const stderrTail = stderr.slice(-8000);
      let parsed: { status?: string; counts?: Record<string, number>; error?: string; type?: string };
      try {
        parsed = parseLastJsonObjectFromStdout(stdout) as typeof parsed;
      } catch {
        const exitDesc = describeLlmWorkerExit(code, signal, timeoutMs);
        reject(
          new PersonaProcessError(`${exitDesc}\n且无法解析 Neo4j 导入 JSON。`, {
            statusCode: 502,
            stderr: stderrTail,
            stdoutPreview: stdout.trim().slice(0, 2000),
          }),
        );
        return;
      }

      if (parsed?.status === "error" || parsed?.error) {
        reject(
          new PersonaProcessError(String(parsed.error || "Neo4j 导入失败"), {
            statusCode: 502,
            stderr: stderrTail,
            errorType: typeof parsed.type === "string" ? parsed.type : undefined,
          }),
        );
        return;
      }

      if (code !== 0 || signal) {
        const exitDesc = describeLlmWorkerExit(code, signal, timeoutMs);
        reject(
          new PersonaProcessError(`${exitDesc}${stderrTail ? `\n${stderrTail.slice(-2500)}` : ""}`, {
            statusCode: 502,
            stderr: stderrTail,
            stdoutPreview: stdout.trim().slice(0, 2000),
          }),
        );
        return;
      }

      resolve({
        status: parsed.status || "ok",
        counts: parsed.counts,
      });
    });

    child.stdin.write(JSON.stringify(payload), "utf8");
    child.stdin.end();
  });
}

export function buildDatasetLabel(params: {
  recsysType: string;
  source: string;
  trends?: unknown[];
}): string {
  const trends = uniqueStrings(Array.isArray(params.trends) ? params.trends : []);
  if (trends.length > 0) {
    return `${params.recsysType.toUpperCase()} ${trends.slice(0, 2).join(" / ")}${trends.length > 2 ? " +" : ""}`;
  }
  return `${params.recsysType.toUpperCase()} ${params.source}`;
}
