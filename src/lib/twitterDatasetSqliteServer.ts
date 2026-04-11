import path from "path";
import { existsSync } from "fs";

const PLATFORM = "twitter";

/** 与 better-sqlite3 / node:sqlite 兼容的最小只读接口 */
export type TwitterSqliteDb = {
  prepare: (sql: string) => {
    all: (...params: unknown[]) => unknown[];
    get?: (...params: unknown[]) => unknown;
  };
  close: () => void;
};

export type TwitterSqliteTopicRow = {
  topic_key: string;
  topic_label: string;
  last_seen_at: string | null;
  post_count: number;
  reply_count: number;
};

export type TwitterSqliteTopicSeedResult = {
  topic_key: string;
  user_limit_requested: number;
  users_selected: number;
  kol_selected: number;
  normal_selected: number;
  counts: {
    users: number;
    posts: number;
    replies: number;
    topics: number;
  };
  external_user_ids: string[];
};

function shuffleInPlace<T>(arr: T[]): void {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
}

function randomSample<T>(arr: T[], n: number): T[] {
  if (n <= 0 || arr.length === 0) return [];
  const copy = [...arr];
  shuffleInPlace(copy);
  return copy.slice(0, Math.min(n, copy.length));
}

function loadUserTypes(db: TwitterSqliteDb, ids: string[]): Map<string, "kol" | "normal"> {
  const m = new Map<string, "kol" | "normal">();
  if (ids.length === 0) return m;
  const ph = ids.map(() => "?").join(", ");
  const rows = db
    .prepare(
      `SELECT external_user_id AS id,
              lower(trim(COALESCE(user_type, 'normal'))) AS ut
       FROM users
       WHERE platform = ? AND external_user_id IN (${ph})`,
    )
    .all(PLATFORM, ...ids) as { id: string; ut: string }[];
  for (const row of rows) {
    m.set(row.id, row.ut === "kol" ? "kol" : "normal");
  }
  return m;
}

/**
 * 在尽量保持人数不变的前提下，用池子里的 normal 替换 S 中「非必留」的 KOL，使 normal >= 10*kol；做不到则放弃。
 */
function relaxKolNormalInSet(
  s: string[],
  types: Map<string, "kol" | "normal">,
  pool: string[],
  mandatory: Set<string>,
): string[] {
  const set = new Set(s);
  const countKol = (ids: Iterable<string>) =>
    [...ids].filter((id) => (types.get(id) ?? "normal") === "kol").length;
  const countNormal = (ids: Iterable<string>) =>
    [...ids].filter((id) => (types.get(id) ?? "normal") !== "kol").length;

  let cur = [...s];
  let guard = 0;
  while (guard++ < 5000) {
    const k = countKol(cur);
    const n = countNormal(cur);
    if (k === 0 || n >= 10 * k) break;
    const victim = cur.find((id) => (types.get(id) ?? "normal") === "kol" && !mandatory.has(id));
    if (!victim) break;
    const replacement = pool.find((id) => !set.has(id) && (types.get(id) ?? "normal") !== "kol");
    if (!replacement) break;
    set.delete(victim);
    set.add(replacement);
    cur = [...set];
  }
  return cur;
}

/** 在 normal >= 10 * kol 且 kol+n 不超过池子容量下，尽量接近 userLimit。 */
export function pickKolNormalCounts(kolPool: number, normalPool: number, userLimit: number): { k: number; n: number } {
  const K = kolPool;
  const P = normalPool;
  const N = Math.max(0, Math.floor(userLimit));
  for (let total = N; total >= 0; total--) {
    const kMax = Math.min(K, Math.floor(total / 11));
    for (let k = kMax; k >= 0; k--) {
      const n = total - k;
      if (n >= 10 * k && n <= P && k <= K) {
        return { k, n };
      }
    }
  }
  return { k: 0, n: 0 };
}

export function resolveTwitterDatasetSqlitePath(projectRoot: string): string {
  const fromEnv = process.env.TWITTER_DATASET_SQLITE_PATH || process.env.OASIS_TWITTER_DATASET_DB;
  if (fromEnv && String(fromEnv).trim()) {
    return path.isAbsolute(fromEnv) ? fromEnv : path.join(projectRoot, fromEnv);
  }
  const dir = path.join(projectRoot, "oasis_dashboard", "datasets");
  const preferred = path.join(dir, "oasis_datasets.db");
  const legacy = path.join(dir, "test_oasis_datasets.db");
  if (existsSync(preferred)) return preferred;
  if (existsSync(legacy)) return legacy;
  return preferred;
}

/**
 * 打开只读 SQLite：优先 Node 内置 `node:sqlite`（无需编译原生模块），失败时再尝试 better-sqlite3。
 */
export async function openTwitterDatasetReadonly(dbPath: string): Promise<TwitterSqliteDb> {
  try {
    const { DatabaseSync } = await import("node:sqlite");
    const db = new DatabaseSync(dbPath, { readOnly: true });
    return db as unknown as TwitterSqliteDb;
  } catch (first: unknown) {
    try {
      const BetterSqlite = (await import("better-sqlite3")).default;
      return new BetterSqlite(dbPath, { readonly: true }) as unknown as TwitterSqliteDb;
    } catch (second: unknown) {
      const a = first instanceof Error ? first.message : String(first);
      const b = second instanceof Error ? second.message : String(second);
      throw new Error(`无法打开 SQLite（已尝试 node:sqlite 与 better-sqlite3）。node:sqlite: ${a}；better-sqlite3: ${b}`);
    }
  }
}

export function listRecentTopicsThenShuffle(
  db: TwitterSqliteDb,
  options: { recentPool: number; minTopics: number },
): { topics: TwitterSqliteTopicRow[]; total_recent: number } {
  const recentPool = Math.max(1, Math.min(500, Math.floor(options.recentPool)));
  const minTopics = Math.max(1, Math.min(200, Math.floor(options.minTopics)));

  const rows = db
    .prepare(
      `SELECT topic_key, topic_label, last_seen_at, post_count, reply_count
       FROM topics
       WHERE platform = ?
       ORDER BY COALESCE(last_seen_at, first_seen_at, '') DESC
       LIMIT ${recentPool}`,
    )
    .all(PLATFORM) as TwitterSqliteTopicRow[];

  shuffleInPlace(rows);
  const topics = rows.slice(0, Math.min(minTopics, rows.length));
  return { topics, total_recent: rows.length };
}

/** 按时间倒序返回近期话题（不随机），用于多选列表 */
export function listRecentTopicsOrdered(db: TwitterSqliteDb, recentPool: number): TwitterSqliteTopicRow[] {
  const n = Math.max(1, Math.min(5000, Math.floor(recentPool)));
  return db
    .prepare(
      `SELECT topic_key, topic_label, last_seen_at, post_count, reply_count
       FROM topics
       WHERE platform = ?
       ORDER BY COALESCE(last_seen_at, first_seen_at, '') DESC
       LIMIT ${n}`,
    )
    .all(PLATFORM) as TwitterSqliteTopicRow[];
}

export function computeTopicSeedSample(db: TwitterSqliteDb, topicKey: string, userLimit: number): TwitterSqliteTopicSeedResult {
  return computeMultiTopicSeedSample(db, [topicKey], userLimit);
}

export function computeMultiTopicSeedSample(db: TwitterSqliteDb, topicKeysIn: string[], userLimit: number): TwitterSqliteTopicSeedResult {
  const N = Math.max(1, Math.min(2000, Math.floor(userLimit)));
  const topicKeys = [...new Set(topicKeysIn.map((k) => String(k).trim()).filter(Boolean))];

  if (topicKeys.length === 0) {
    return {
      topic_key: "",
      user_limit_requested: N,
      users_selected: 0,
      kol_selected: 0,
      normal_selected: 0,
      counts: { users: 0, posts: 0, replies: 0, topics: 0 },
      external_user_ids: [],
    };
  }

  const tkPh = topicKeys.map(() => "?").join(", ");
  const postRows = db
    .prepare(
      `SELECT DISTINCT c.external_content_id AS pid, c.author_external_user_id AS aid
       FROM contents c
       INNER JOIN content_topics ct
         ON ct.platform = c.platform AND ct.external_content_id = c.external_content_id
       INNER JOIN users u
         ON u.platform = c.platform AND u.external_user_id = c.author_external_user_id
       WHERE c.platform = ? AND c.content_type = 'post'
         AND ct.topic_key IN (${tkPh})
         AND c.author_external_user_id IS NOT NULL
         AND TRIM(c.author_external_user_id) != ''`,
    )
    .all(PLATFORM, ...topicKeys) as { pid: string; aid: string }[];

  const postIds = [...new Set(postRows.map((r) => r.pid))];
  const postAuthorList = [...new Set(postRows.map((r) => r.aid))];
  const postCount = postIds.length;

  let replyCount = 0;
  const replyAuthorSet = new Set<string>();
  if (postIds.length > 0) {
    const pPh = postIds.map(() => "?").join(", ");
    const stmt = db.prepare(
      `SELECT COUNT(*) AS c
       FROM contents c
       WHERE c.platform = ? AND c.content_type = 'reply'
         AND (
           (c.root_external_content_id IS NOT NULL AND c.root_external_content_id IN (${pPh}))
           OR (c.parent_external_content_id IS NOT NULL AND c.parent_external_content_id IN (${pPh}))
         )`,
    );
    const rc = (typeof stmt.get === "function"
      ? stmt.get(PLATFORM, ...postIds, ...postIds)
      : stmt.all(PLATFORM, ...postIds, ...postIds)[0]) as { c: number };
    replyCount = Number(rc?.c) || 0;

    const raRows = db
      .prepare(
        `SELECT DISTINCT c.author_external_user_id AS aid
         FROM contents c
         INNER JOIN users u
           ON u.platform = c.platform AND u.external_user_id = c.author_external_user_id
         WHERE c.platform = ? AND c.content_type = 'reply'
           AND (
             (c.root_external_content_id IS NOT NULL AND c.root_external_content_id IN (${pPh}))
             OR (c.parent_external_content_id IS NOT NULL AND c.parent_external_content_id IN (${pPh}))
           )
           AND c.author_external_user_id IS NOT NULL
           AND TRIM(c.author_external_user_id) != ''`,
      )
      .all(PLATFORM, ...postIds, ...postIds) as { aid: string }[];
    for (const r of raRows) replyAuthorSet.add(r.aid);
  }

  const postAuthorSet = new Set(postAuthorList);
  const replyOnlyAuthors = [...replyAuthorSet].filter((id) => !postAuthorSet.has(id));

  const candidatePool = [...new Set([...postAuthorList, ...replyOnlyAuthors])];
  const types = loadUserTypes(db, candidatePool);

  const P = postAuthorList.filter((id) => types.has(id));
  const R = replyOnlyAuthors.filter((id) => types.has(id));

  let chosen: string[] = [];
  /** 比例调整时不可移出集合的用户（须保留的帖子作者） */
  let mandatory = new Set<string>();

  if (postCount === 0) {
    chosen = [];
  } else if (N < postCount) {
    chosen = randomSample(P, Math.min(N, P.length));
    mandatory = new Set();
  } else {
    if (P.length >= N) {
      chosen = randomSample(P, N);
      mandatory = new Set(chosen);
    } else {
      chosen = [...P, ...randomSample(R, Math.min(N - P.length, R.length))];
      mandatory = new Set(P);
    }
  }

  const poolForRatio = [...new Set([...P, ...R])];
  chosen = relaxKolNormalInSet(chosen, types, poolForRatio, mandatory);

  const kolSel = chosen.filter((id) => (types.get(id) ?? "normal") === "kol").length;
  const normalSel = chosen.length - kolSel;

  return {
    topic_key: topicKeys.length === 1 ? topicKeys[0] : topicKeys.join("\t"),
    user_limit_requested: N,
    users_selected: chosen.length,
    kol_selected: kolSel,
    normal_selected: normalSel,
    counts: {
      users: chosen.length,
      posts: postCount,
      replies: replyCount,
      topics: topicKeys.length,
    },
    external_user_ids: chosen,
  };
}

function fetchContentFallbackForAuthor(
  db: TwitterSqliteDb,
  authorId: string,
  maxPosts: number,
  maxReplies: number,
  maxTotalChars: number,
): string {
  const postRows = db
    .prepare(
      `SELECT COALESCE(text, '') AS t
       FROM contents
       WHERE platform = ? AND author_external_user_id = ? AND content_type = 'post'
         AND text IS NOT NULL AND TRIM(text) != ''
       ORDER BY datetime(COALESCE(created_at, '')) DESC
       LIMIT ?`,
    )
    .all(PLATFORM, authorId, maxPosts) as { t: string }[];

  const replyRows = db
    .prepare(
      `SELECT COALESCE(text, '') AS t
       FROM contents
       WHERE platform = ? AND author_external_user_id = ? AND content_type = 'reply'
         AND text IS NOT NULL AND TRIM(text) != ''
       ORDER BY datetime(COALESCE(created_at, '')) DESC
       LIMIT ?`,
    )
    .all(PLATFORM, authorId, maxReplies) as { t: string }[];

  const parts: string[] = [];
  const postTexts = postRows.map((r) => String(r.t || "").trim()).filter(Boolean);
  if (postTexts.length) {
    parts.push("【发帖摘录】");
    parts.push(...postTexts);
  }
  const replyTexts = replyRows.map((r) => String(r.t || "").trim()).filter(Boolean);
  if (replyTexts.length) {
    parts.push("【评论摘录】");
    parts.push(...replyTexts);
  }
  return parts.join("\n").trim().slice(0, maxTotalChars);
}

/** 为 LLM persona 子进程组装 seed_users：含 name / username / bio；无 bio 时用发帖与评论文本写入 description */
export function getTopicLabelsForKeys(db: TwitterSqliteDb, topicKeys: string[]): { topic_key: string; topic_label: string }[] {
  const keys = [...new Set(topicKeys.map((k) => String(k).trim()).filter(Boolean))];
  if (!keys.length) return [];
  const ph = keys.map(() => "?").join(", ");
  const rows = db
    .prepare(
      `SELECT topic_key, topic_label FROM topics WHERE platform = ? AND topic_key IN (${ph})`,
    )
    .all(PLATFORM, ...keys) as { topic_key: string; topic_label: string }[];
  const byKey = new Map(rows.map((r) => [r.topic_key, r.topic_label]));
  return keys.map((k) => ({ topic_key: k, topic_label: byKey.get(k) || k }));
}

export function buildSeedUsersForLlmFromSqlite(db: TwitterSqliteDb, externalUserIds: string[]): Record<string, unknown>[] {
  const ids = [...new Set(externalUserIds.map((x) => String(x).trim()).filter(Boolean))];
  if (!ids.length) return [];
  const ph = ids.map(() => "?").join(", ");
  const rows = db
    .prepare(
      `SELECT external_user_id, username, display_name, bio,
              lower(trim(COALESCE(user_type, 'normal'))) AS ut
       FROM users
       WHERE platform = ? AND external_user_id IN (${ph})`,
    )
    .all(PLATFORM, ...ids) as {
    external_user_id: string;
    username: string | null;
    display_name: string | null;
    bio: string | null;
    ut: string;
  }[];

  const seeds: Record<string, unknown>[] = [];
  for (const row of rows) {
    const bio = String(row.bio || "").trim();
    const uname = String(row.username || "").trim() || `user_${row.external_user_id}`;
    const display = String(row.display_name || "").trim() || uname;
    const ut = row.ut === "kol" ? "kol" : "normal";
    let description = bio;
    if (!bio) {
      description = fetchContentFallbackForAuthor(db, row.external_user_id, 8, 8, 2400);
    }
    seeds.push({
      twitter_user_id: row.external_user_id,
      username: uname,
      user_name: uname,
      name: display,
      bio: bio || "",
      description: (description || display).slice(0, 4000),
      user_type: ut,
    });
  }
  return seeds;
}

export function assertSqliteDbReadable(dbPath: string): void {
  if (!existsSync(dbPath)) {
    const err = new Error(
      `Twitter 数据集 SQLite 不存在: ${dbPath}（请将库放在 oasis_dashboard/datasets/oasis_datasets.db，或设置 TWITTER_DATASET_SQLITE_PATH）`,
    );
    (err as Error & { code?: string }).code = "SQLITE_DB_MISSING";
    throw err;
  }
}
