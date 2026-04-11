import { createHash } from "crypto";

/** 可写 SQLite：与只读封装一致，增加 prepare().run */
export type TwitterSqliteRwDb = {
  prepare: (sql: string) => {
    all: (...params: unknown[]) => unknown[];
    get?: (...params: unknown[]) => unknown;
    run: (...params: unknown[]) => { changes?: number };
  };
  exec: (sql: string) => void;
  close: () => void;
};

export async function openTwitterDatasetReadWrite(dbPath: string): Promise<TwitterSqliteRwDb> {
  try {
    const BetterSqlite = (await import("better-sqlite3")).default;
    const db = BetterSqlite(dbPath);
    return {
      prepare(sql: string) {
        const stmt = db.prepare(sql);
        return {
          all: (...params: unknown[]) => stmt.all(...(params as never[])) as unknown[],
          get: (...params: unknown[]) => stmt.get(...(params as never[])) as unknown,
          run: (...params: unknown[]) => {
            const r = stmt.run(...(params as never[]));
            return { changes: Number((r as { changes?: number | bigint }).changes ?? 0) };
          },
        };
      },
      exec: (sql: string) => {
        db.exec(sql);
      },
      close: () => {
        db.close();
      },
    };
  } catch {
    const { DatabaseSync } = await import("node:sqlite");
    const db = new DatabaseSync(dbPath, { readOnly: false });
    return {
      prepare(sql: string) {
        const stmt = db.prepare(sql);
        return {
          all: (...params: unknown[]) => stmt.all(...(params as never[])) as unknown[],
          get: (...params: unknown[]) => stmt.get(...(params as never[])) as unknown,
          run: (...params: unknown[]) => {
            const r = stmt.run(...(params as never[]));
            return { changes: Number((r as { changes?: number | bigint }).changes ?? 0) };
          },
        };
      },
      exec: (sql: string) => {
        db.exec(sql);
      },
      close: () => {
        db.close();
      },
    };
  }
}

const LLM_PLATFORM = "llm";

function tableExists(db: TwitterSqliteRwDb, name: string): boolean {
  const row = db.prepare(`SELECT 1 AS x FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1`).get(name);
  return Boolean(row);
}

function listColumnNames(db: TwitterSqliteRwDb, table: string): Set<string> {
  const rows = db.prepare(`PRAGMA table_info(${table})`).all() as { name: string }[];
  return new Set(rows.map((r) => String(r.name)));
}

/** 仅保留表中存在的列；键名大小写不敏感，写入使用 PRAGMA 中的规范列名 */
function projectRowToTable(row: Record<string, unknown>, tableCols: Set<string>): Record<string, unknown> {
  const lowerToCanon = new Map<string, string>();
  for (const c of tableCols) lowerToCanon.set(c.toLowerCase(), c);
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) {
    if (v === undefined) continue;
    const canon = lowerToCanon.get(k.toLowerCase());
    if (canon) out[canon] = v;
  }
  return out;
}

/** 稳定外部 id，写入 topics.news_external_id（原先用作 topic_key 的 llm_t_…） */
function stableNewsExternalId(title: string, index: number): string {
  const h = createHash("sha1").update(`${title}\0${index}`).digest("hex").slice(0, 20);
  return `llm_t_${h}`;
}

function topicKeyFromLabel(topicLabel: string): string {
  return topicLabel.trim().toLowerCase();
}

/** 仿真话题 topic_key 集合（与 topics.topic_key = topic_label 小写一致），供 user_topics 校验 */
function buildSyntheticTopicKeySet(topics: Array<{ title: string; summary: string }>): Set<string> {
  const s = new Set<string>();
  for (const t of topics) {
    const label = String(t.title ?? "").trim();
    if (label) s.add(topicKeyFromLabel(label));
  }
  return s;
}

function buildTopicRowCandidates(
  topics: Array<{ title: string; summary: string }>,
): Record<string, unknown>[] {
  const now = new Date().toISOString();
  return topics.map((t, idx) => {
    const title = String(t.title ?? "").trim() || `topic_${idx}`;
    const summary = String(t.summary ?? "").trim();
    const topic_label = title;
    const topic_key = topicKeyFromLabel(topic_label);
    const base: Record<string, unknown> = {
      platform: LLM_PLATFORM,
      type: LLM_PLATFORM,
      topic_type: LLM_PLATFORM,
      topic_key,
      topic_label,
      news_external_id: stableNewsExternalId(title, idx),
      last_seen_at: now,
      first_seen_at: now,
      post_count: 0,
      reply_count: 0,
    };
    if (summary) {
      base.summary = summary;
      base.description = summary;
      base.topic_summary = summary;
    }
    return base;
  });
}

/**
 * raw_json.agent_id：与 users.external_user_id 同源（twitter_user_id / external_user_id），不自增序号。
 * 纯数字且在 JS 安全整数内则写为 number，否则写为 string（避免 Twitter snowflake 精度丢失、或 llm_ 前缀 id）。
 */
function agentIdForRawJson(doc: Record<string, unknown>): string | number | null {
  const ext = String(doc.twitter_user_id ?? doc.external_user_id ?? "").trim();
  if (!ext) return null;
  if (/^\d+$/.test(ext)) {
    const n = Number(ext);
    if (Number.isSafeInteger(n)) return n;
    return ext;
  }
  return ext;
}

/** 优先 doc.location，否则 profile.other_info.country（与 Twitter 语义一致）。 */
function resolveLocationPlain(doc: Record<string, unknown>, oi: Record<string, unknown>): string {
  const explicit = doc.location != null ? String(doc.location).trim() : "";
  if (explicit) return explicit;
  return oi.country != null ? String(oi.country).trim() : "";
}

/** 与线 Twitter 用户 raw_json 结构对齐，供 users.raw_json 列写入（仅含可确定字段，其余 null）。有 country 时 location 用同文案，避免 location 空而 country 有值。 */
function buildRawJsonFromLlmUser(doc: Record<string, unknown>): Record<string, unknown> {
  const profile = doc.profile;
  const oi =
    typeof profile === "object" && profile !== null
      ? (((profile as Record<string, unknown>).other_info as Record<string, unknown>) ?? {})
      : {};
  const topicsList = Array.isArray(oi.topics) ? (oi.topics as unknown[]).map((x) => String(x)) : [];

  const otherInfo: Record<string, unknown> = {
    topics: topicsList,
    gender: oi.gender ?? null,
    age: oi.age ?? null,
    mbti: oi.mbti ?? null,
    country: oi.country ?? null,
  };
  if (typeof oi.user_profile === "string" && oi.user_profile.trim()) {
    otherInfo.user_profile = oi.user_profile;
  }

  const locationPlain = resolveLocationPlain(doc, oi);
  const location = locationPlain || null;

  return {
    agent_id: agentIdForRawJson(doc),
    user_name: String(doc.user_name ?? ""),
    name: String(doc.name ?? ""),
    description: String(doc.description ?? ""),
    profile: {
      other_info: otherInfo,
    },
    recsys_type: String(doc.recsys_type ?? "twitter"),
    user_type: String(oi.user_type ?? doc.user_type ?? "normal"),
    twitter_user_id: String(doc.twitter_user_id ?? doc.external_user_id ?? ""),
    followers_count: null,
    following_count: null,
    tweet_count: null,
    verified: false,
    verified_followers_count: null,
    location,
    source_topics: topicsList,
  };
}

function buildUserRowCandidate(doc: Record<string, unknown>): Record<string, unknown> {
  const profile = (doc.profile as Record<string, unknown> | undefined) ?? {};
  const oi = (profile.other_info as Record<string, unknown> | undefined) ?? {};
  const topicsArr = Array.isArray(oi.topics) ? oi.topics : [];
  const base: Record<string, unknown> = {
    platform: LLM_PLATFORM,
    type: LLM_PLATFORM,
    external_user_id: String(doc.twitter_user_id ?? doc.external_user_id ?? "").trim(),
    username: String(doc.user_name ?? doc.username ?? "").trim(),
    display_name: String(doc.name ?? "").trim(),
    bio: String(doc.description ?? "").trim(),
    user_type: String(oi.user_type ?? doc.user_type ?? "normal").toLowerCase(),
    gender: oi.gender ?? null,
    age:
      typeof oi.age === "number" && Number.isFinite(oi.age)
        ? Math.round(oi.age)
        : typeof oi.age === "string" && /^\d+$/.test(oi.age)
          ? Number(oi.age)
          : undefined,
    mbti: oi.mbti != null ? String(oi.mbti) : null,
    country: oi.country != null ? String(oi.country) : null,
    location: resolveLocationPlain(doc, oi) || "",
    dataset_id: doc.dataset_id != null ? String(doc.dataset_id) : null,
    recsys_type: doc.recsys_type != null ? String(doc.recsys_type) : null,
    source: doc.source != null ? String(doc.source) : null,
    ingest_status: doc.ingest_status != null ? String(doc.ingest_status) : null,
    raw_json: JSON.stringify(buildRawJsonFromLlmUser(doc)),
  };
  if (topicsArr.length) {
    const json = JSON.stringify(topicsArr);
    base.topics_json = json;
    base.interests_json = json;
    base.profile_json = typeof doc.profile === "object" && doc.profile !== null ? JSON.stringify(doc.profile) : null;
  } else if (typeof doc.profile === "object" && doc.profile !== null) {
    base.profile_json = JSON.stringify(doc.profile);
  }
  return base;
}

function upsertUserTopicsRow(db: TwitterSqliteRwDb, row: Record<string, unknown>): void {
  const platform = String(row.platform ?? LLM_PLATFORM);
  const topicKey = String(row.topic_key ?? "");
  const extId = String(row.external_user_id ?? "");
  if (!topicKey || !extId) return;

  const stmt = db.prepare(
    `SELECT 1 AS x FROM user_topics WHERE platform = ? AND topic_key = ? AND external_user_id = ? LIMIT 1`,
  );
  const exists = stmt.get ? stmt.get(platform, topicKey, extId) : stmt.all(platform, topicKey, extId)[0];
  const hasRow = exists != null;

  const cols = Object.keys(row);
  const vals = cols.map((c) => row[c]);

  if (hasRow) {
    const mutable = cols.filter((c) => c !== "platform" && c !== "topic_key" && c !== "external_user_id");
    if (!mutable.length) return;
    const setSql = mutable.map((c) => `"${c.replace(/"/g, '""')}" = ?`).join(", ");
    const params = [...mutable.map((c) => row[c]), platform, topicKey, extId];
    db.prepare(`UPDATE user_topics SET ${setSql} WHERE platform = ? AND topic_key = ? AND external_user_id = ?`).run(
      ...params,
    );
  } else {
    const colSql = cols.map((c) => `"${c.replace(/"/g, '""')}"`).join(", ");
    const ph = cols.map(() => "?").join(", ");
    db.prepare(`INSERT INTO user_topics (${colSql}) VALUES (${ph})`).run(...vals);
  }
}

function upsertRow(
  db: TwitterSqliteRwDb,
  table: "topics" | "users",
  keyColumn: "topic_key" | "external_user_id",
  row: Record<string, unknown>,
): void {
  const platform = String(row.platform ?? LLM_PLATFORM);
  const keyVal = String(row[keyColumn] ?? "");
  if (!keyVal) return;

  const stmt = db.prepare(`SELECT 1 AS x FROM ${table} WHERE platform = ? AND ${keyColumn} = ? LIMIT 1`);
  const exists = stmt.get ? stmt.get(platform, keyVal) : stmt.all(platform, keyVal)[0];
  const hasRow = exists != null;

  const cols = Object.keys(row);
  const vals = cols.map((c) => row[c]);

  if (hasRow) {
    const mutable = cols.filter((c) => c !== "platform" && c !== keyColumn);
    if (!mutable.length) return;
    const setSql = mutable.map((c) => `"${c.replace(/"/g, '""')}" = ?`).join(", ");
    const params = [...mutable.map((c) => row[c]), platform, keyVal];
    db.prepare(`UPDATE ${table} SET ${setSql} WHERE platform = ? AND ${keyColumn} = ?`).run(...params);
  } else {
    const colSql = cols.map((c) => `"${c.replace(/"/g, '""')}"`).join(", ");
    const ph = cols.map(() => "?").join(", ");
    db.prepare(`INSERT INTO ${table} (${colSql}) VALUES (${ph})`).run(...vals);
  }
}

export type SqliteLlmPersistResult = {
  ok: boolean;
  error?: string;
  topics_upserted: number;
  users_upserted: number;
  user_topics_upserted: number;
};

/**
 * 将大模型生成的仿真话题与用户写入本地 SQLite。
 * - 仅写入目标表中已存在的列（PRAGMA table_info）。
 * - users：platform、type 固定为 llm（若表无 type 列则仅写 platform，type 键会在投影时丢弃）。
 * - user_topics：用户 profile 中 topics 与仿真话题 title 对应时，topic_key 为 title 小写（与 topics 表一致）。
 * - topics：topic_key = topic_label 小写；news_external_id = 稳定 llm_t_… id。
 * - users：raw_json 为与采集用户相近的 JSON 结构。
 */
export async function persistLlmTopicsAndUsersSqlite(
  dbPath: string,
  input: {
    topics: Array<{ title: string; summary: string }>;
    users: Record<string, unknown>[];
  },
): Promise<SqliteLlmPersistResult> {
  let db: TwitterSqliteRwDb | null = null;
  try {
    db = await openTwitterDatasetReadWrite(dbPath);
    db.exec("BEGIN IMMEDIATE");

    let topicsUpserted = 0;
    let usersUpserted = 0;
    let userTopicsUpserted = 0;

    const syntheticTopicKeys = buildSyntheticTopicKeySet(input.topics);

    if (input.topics.length && tableExists(db, "topics")) {
      const topicCols = listColumnNames(db, "topics");
      for (const cand of buildTopicRowCandidates(input.topics)) {
        const row = projectRowToTable(cand, topicCols);
        if (!row.topic_key || !row.platform) continue;
        upsertRow(db, "topics", "topic_key", row);
        topicsUpserted += 1;
      }
    }

    if (input.users.length && tableExists(db, "users")) {
      const userCols = listColumnNames(db, "users");
      for (const doc of input.users) {
        if (!doc || typeof doc !== "object") continue;
        const cand = buildUserRowCandidate(doc as Record<string, unknown>);
        const row = projectRowToTable(cand, userCols);
        if (!row.external_user_id || !row.platform) continue;
        upsertRow(db, "users", "external_user_id", row);
        usersUpserted += 1;
      }
    }

    if (input.topics.length && input.users.length && tableExists(db, "user_topics") && syntheticTopicKeys.size > 0) {
      const utCols = listColumnNames(db, "user_topics");
      for (const doc of input.users) {
        if (!doc || typeof doc !== "object") continue;
        const d = doc as Record<string, unknown>;
        const extId = String(d.twitter_user_id ?? d.external_user_id ?? "").trim();
        if (!extId) continue;
        const profile = (d.profile as Record<string, unknown> | undefined) ?? {};
        const oi = (profile.other_info as Record<string, unknown> | undefined) ?? {};
        const interestTitles = Array.isArray(oi.topics) ? oi.topics.map((x) => String(x).trim()) : [];
        for (const title of interestTitles) {
          if (!title) continue;
          const topicKey = topicKeyFromLabel(title);
          if (!syntheticTopicKeys.has(topicKey)) continue;
          const cand: Record<string, unknown> = {
            platform: LLM_PLATFORM,
            topic_key: topicKey,
            external_user_id: extId,
            role: "llm_interest",
            content_count: 1,
            type: LLM_PLATFORM,
          };
          const row = projectRowToTable(cand, utCols);
          if (!row.platform || !row.topic_key || !row.external_user_id) continue;
          if (!row.role) continue;
          upsertUserTopicsRow(db, row);
          userTopicsUpserted += 1;
        }
      }
    }

    db.exec("COMMIT");
    db.close();
    db = null;
    return {
      ok: true,
      topics_upserted: topicsUpserted,
      users_upserted: usersUpserted,
      user_topics_upserted: userTopicsUpserted,
    };
  } catch (e) {
    try {
      db?.exec("ROLLBACK");
    } catch {
      /* ignore */
    }
    try {
      db?.close();
    } catch {
      /* ignore */
    }
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, error: msg, topics_upserted: 0, users_upserted: 0, user_topics_upserted: 0 };
  }
}
