/**
 * 根据 users.json、relationships.json、topics.json 构建力导向图可用的
 * nodes / edges；话题节点落在中心小圆盘内，各话题下的用户落在以该话题为圆心的小圆盘内。
 *
 * 关系边：follow / friend 均视为社交网络中的「实线」边（origin: real）。
 * 黄色虚线仅用于 isolated_bridge：孤立或弱连接用户与网络枢纽（优先 KOL）的示意连线。
 */

export type SocialGraphBundle = {
  users: unknown;
  relationships: unknown[];
  topics: { data?: Array<{ category?: string; topics?: string[] }> } | null;
  metrics?: Record<string, unknown>;
};

function diskPoint(cx: number, cy: number, radius: number, rng: () => number) {
  const t = 2 * Math.PI * rng();
  const r = radius * Math.sqrt(rng());
  return { x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) };
}

function coerceUsers(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) return data as Array<Record<string, unknown>>;
  if (data && typeof data === "object" && Array.isArray((data as { data?: unknown[] }).data)) {
    return (data as { data: Array<Record<string, unknown>> }).data;
  }
  return [];
}

/** 与 ``users.json`` 中每条用户记录一致：只认顶层 ``user_type``（kol / normal）。 */
export function userTypeFromUsersJsonRecord(u: Record<string, unknown>): "kol" | "normal" {
  const ut = String(u.user_type ?? "").trim().toLowerCase();
  return ut === "kol" ? "kol" : "normal";
}

function collectTopicTitles(topicsDoc: SocialGraphBundle["topics"]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  if (!topicsDoc?.data) return out;
  for (const block of topicsDoc.data) {
    const list = Array.isArray(block.topics) ? block.topics : [];
    for (const t of list) {
      const s = String(t).trim();
      if (s && !seen.has(s)) {
        seen.add(s);
        out.push(s);
      }
    }
  }
  return out;
}

function topicNodeId(title: string, index: number) {
  return `topic:${index}:${title.slice(0, 80)}`;
}

function isUserNodeId(id: string) {
  return id.startsWith("user_");
}

/** 整体放大系数，拉开话题簇与用户环带 */
const LAYOUT_SCALE = 1.52;

export function buildLocalSocialGraphLayout(bundle: SocialGraphBundle, seed = 42) {
  let s = seed;
  const rng = () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };

  const users = coerceUsers(bundle.users);
  const rels = Array.isArray(bundle.relationships) ? bundle.relationships : [];
  const topicTitles = collectTopicTitles(bundle.topics);

  const topicDiskR = 52;
  const userDiskR = 138;
  const topicClusterR = 72;

  const topicPositions = new Map<string, { x: number; y: number }>();
  topicTitles.forEach((title) => {
    const p = diskPoint(0, 0, topicClusterR, rng);
    topicPositions.set(title, p);
  });

  const nodes: any[] = [];
  const edges: any[] = [];

  for (let i = 0; i < topicTitles.length; i++) {
    const title = topicTitles[i];
    const { x, y } = topicPositions.get(title) || { x: 0, y: 0 };
    const jitter = diskPoint(x, y, topicDiskR * 0.38, rng);
    const sx = jitter.x * LAYOUT_SCALE;
    const sy = jitter.y * LAYOUT_SCALE;
    const id = topicNodeId(title, i);
    nodes.push({
      id,
      name: title,
      type: "topic",
      heat: "High",
      source: "topics.json",
      x: sx,
      y: sy,
      homeX: sx,
      homeY: sy,
    });
  }

  const primaryTopicForUser = (u: Record<string, unknown>): string | null => {
    const prof = u.profile as { other_info?: { topics?: unknown[] } } | undefined;
    const topics = prof?.other_info?.topics;
    if (!Array.isArray(topics)) return topicTitles[0] ?? null;
    for (const t of topics) {
      const key = String(t).trim();
      if (key && topicPositions.has(key)) return key;
    }
    return topicTitles[0] ?? null;
  };

  for (const u of users) {
    const aid = Number(u.agent_id);
    if (!Number.isFinite(aid)) continue;
    const uid = `user_${aid}`;
    const name = String(u.name || u.user_name || uid);
    const desc = String(u.description || "");
    const userType = userTypeFromUsersJsonRecord(u);
    const prof = u.profile as { other_info?: { topics?: string[] } } | undefined;
    const interests = Array.isArray(prof?.other_info?.topics)
      ? prof!.other_info!.topics!.map((x) => String(x))
      : [];
    const pt = primaryTopicForUser(u);
    const center = pt ? topicPositions.get(pt) || { x: 0, y: 0 } : { x: 0, y: 0 };
    const scaledCenter = { x: center.x * LAYOUT_SCALE, y: center.y * LAYOUT_SCALE };
    const pos = diskPoint(scaledCenter.x, scaledCenter.y, userDiskR, rng);
    nodes.push({
      id: uid,
      name,
      type: "agent",
      user_type: userType,
      bio: desc,
      interests,
      x: pos.x,
      y: pos.y,
      homeX: pos.x,
      homeY: pos.y,
    });
    if (pt) {
      const ti = topicTitles.indexOf(pt);
      const tid = topicNodeId(pt, ti >= 0 ? ti : 0);
      edges.push({
        source: uid,
        target: tid,
        type: "topic_link",
        origin: "topic",
      });
    }
  }

  const nodeIds = new Set(nodes.map((n) => n.id));

  for (const r of rels) {
    if (!r || typeof r !== "object") continue;
    const from = String((r as { fromUserId?: string }).fromUserId || "");
    const to = String((r as { toUserId?: string }).toUserId || "");
    if (!from || !to || !nodeIds.has(from) || !nodeIds.has(to)) continue;
    if (!isUserNodeId(from) || !isUserNodeId(to)) continue;
    const typ = String((r as { type?: string }).type || "follow");
    edges.push({
      source: from,
      target: to,
      type: typ,
      origin: "real",
    });
  }

  const socialDegree = new Map<string, number>();
  for (const e of edges) {
    const a = String(e.source);
    const b = String(e.target);
    if (e.type === "topic_link") continue;
    if (!isUserNodeId(a) || !isUserNodeId(b)) continue;
    socialDegree.set(a, (socialDegree.get(a) || 0) + 1);
    socialDegree.set(b, (socialDegree.get(b) || 0) + 1);
  }

  const hubCandidates: string[] = [];
  for (const u of users) {
    const aid = Number(u.agent_id);
    if (!Number.isFinite(aid)) continue;
    const uid = `user_${aid}`;
    if (!nodeIds.has(uid)) continue;
    if (userTypeFromUsersJsonRecord(u) === "kol") hubCandidates.push(uid);
  }
  if (hubCandidates.length === 0) {
    const sorted = [...users]
      .map((u) => Number(u.agent_id))
      .filter((x) => Number.isFinite(x))
      .slice(0, 16)
      .map((aid) => `user_${aid}`);
    for (const uid of sorted) {
      if (nodeIds.has(uid)) hubCandidates.push(uid);
    }
  }
  hubCandidates.sort((a, b) => (socialDegree.get(b) || 0) - (socialDegree.get(a) || 0));

  const pickHubs = (avoid: string, count: number): string[] => {
    const pool = hubCandidates.filter((h) => h !== avoid);
    if (pool.length === 0) return [];
    const out: string[] = [];
    const used = new Set<string>();
    let guard = 0;
    while (out.length < count && out.length < pool.length && guard < 64) {
      guard += 1;
      const h = pool[Math.floor(rng() * pool.length)];
      if (!used.has(h)) {
        used.add(h);
        out.push(h);
      }
    }
    return out;
  };

  const bridgeKey = (a: string, b: string) => `${a}::${b}`;
  const existingPairs = new Set<string>();
  for (const e of edges) {
    const x = String(e.source);
    const y = String(e.target);
    existingPairs.add(bridgeKey(x, y));
    existingPairs.add(bridgeKey(y, x));
  }

  const addBridge = (from: string, to: string) => {
    if (from === to) return;
    const k1 = bridgeKey(from, to);
    if (existingPairs.has(k1)) return;
    existingPairs.add(k1);
    existingPairs.add(bridgeKey(to, from));
    edges.push({
      source: from,
      target: to,
      type: "isolated_bridge",
      origin: "isolated_bridge",
    });
  };

  for (const n of nodes) {
    if (n.type !== "agent") continue;
    const uid = n.id as string;
    const d = socialDegree.get(uid) || 0;
    if (d === 0) {
      for (const h of pickHubs(uid, 3)) addBridge(uid, h);
    } else if (d === 1) {
      for (const h of pickHubs(uid, 2)) addBridge(uid, h);
    }
  }

  return { nodes, edges, fixedLayout: true as const };
}
