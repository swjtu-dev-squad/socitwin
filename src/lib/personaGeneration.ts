import type { DatasetCounts, PersonaDatasetManifest, PersonaRawType } from "./personaBackend";
import { createGenerationId } from "./personaBackend";

type RawDataset = Record<PersonaRawType, Record<string, any>[]>;

type SyntheticRule = {
  rule: string;
  trigger: string;
  description: string;
};

type FeatureWeights = {
  topic_overlap: number;
  description_similarity: number;
  recent_text_similarity: number;
  activity_similarity: number;
  followers_similarity: number;
};

export interface GenerationOptions {
  algorithm?: string;
  agentCount?: number;
}

export interface GeneratedAgentDocument {
  generation_id: string;
  dataset_id: string;
  algorithm: string;
  generated_agent_id: number;
  source_user_key: string;
  user_name: string;
  name: string;
  description: string;
  profile: {
    other_info: {
      user_profile: string;
      topics: string[];
      gender: string | null;
      age: number | null;
      mbti: string | null;
      country: string | null;
    };
  };
  recsys_type: string;
  user_type: string;
  interests: string[];
  metadata: Record<string, any>;
  created_at: string;
}

export interface GeneratedGraphDocument {
  generation_id: string;
  dataset_id: string;
  algorithm: string;
  nodes: Array<Record<string, any>>;
  edges: Array<Record<string, any>>;
  stats: {
    nodeCount: number;
    edgeCount: number;
    density: number;
    agentCount: number;
    topicCount: number;
    realEdgeCount: number;
    syntheticEdgeCount: number;
  };
  algorithm_explanation: {
    algorithm: string;
    version: string;
    real_edge_sources: string[];
    synthetic_edge_rules: SyntheticRule[];
    feature_weights: FeatureWeights;
    persona_enrichment_mode: string;
  };
  created_at: string;
}

export interface GenerationBuildResult {
  generationId: string;
  generatedAgents: GeneratedAgentDocument[];
  graphDocument: GeneratedGraphDocument;
}

type SourceUserFeature = {
  userKey: string;
  rawUser: Record<string, any>;
  userName: string;
  name: string;
  description: string;
  topics: string[];
  country: string | null;
  gender: string | null;
  age: number | null;
  mbti: string | null;
  followersCount: number;
  activityCount: number;
  recentTexts: string[];
  descriptionTokens: Set<string>;
  recentTextTokens: Set<string>;
  topicTokens: Set<string>;
  userType: string;
};

type GeneratedAgentFeature = SourceUserFeature & {
  generatedId: number;
  personaText: string;
  syntheticVariant: number;
  generatedUserName: string;
  generatedName: string;
  generatedDescription: string;
};

const FEATURE_WEIGHTS: FeatureWeights = {
  topic_overlap: 0.32,
  description_similarity: 0.18,
  recent_text_similarity: 0.25,
  activity_similarity: 0.15,
  followers_similarity: 0.10,
};

const PERSONA_VERSION = "profiles-real-data-v3";

function nowIso(): string {
  return new Date().toISOString();
}

function normalizeString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeScalar(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return "";
}

function normalizeStringArray(values: unknown[]): string[] {
  return Array.from(
    new Set(
      values
        .map((value) => normalizeString(value))
        .filter(Boolean),
    ),
  );
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function tokenize(text: string): Set<string> {
  const tokens = text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[^a-z0-9_@#]+/g, " ")
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length >= 3);
  return new Set(tokens);
}

function setOverlapScore(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let overlap = 0;
  for (const token of a) {
    if (b.has(token)) overlap += 1;
  }
  return overlap / Math.max(a.size, b.size);
}

function normalizedDifferenceScore(a: number, b: number): number {
  const maxValue = Math.max(a, b, 1);
  return Math.max(0, 1 - Math.abs(a - b) / maxValue);
}

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function deriveUserKey(doc: Record<string, any>): string {
  return (
    normalizeString(doc.twitter_user_id) ||
    normalizeString(doc.external_id) ||
    normalizeString(doc.user_name) ||
    `raw-user-${normalizeScalar(doc.agent_id) || normalizeString(doc.name) || "unknown"}`
  );
}

function buildUserLookups(users: Record<string, any>[]) {
  const byUserKey = new Map<string, Record<string, any>>();
  const byAgentId = new Map<string, string>();
  const byTwitterUserId = new Map<string, string>();
  const byUserName = new Map<string, string>();

  for (const user of users) {
    const userKey = deriveUserKey(user);
    byUserKey.set(userKey, user);

    const agentId = normalizeScalar(user.agent_id);
    if (agentId) byAgentId.set(agentId, userKey);

    const twitterUserId = normalizeString(user.twitter_user_id);
    if (twitterUserId) byTwitterUserId.set(twitterUserId, userKey);

    const userName = normalizeString(user.user_name).toLowerCase();
    if (userName) byUserName.set(userName, userKey);
  }

  return { byUserKey, byAgentId, byTwitterUserId, byUserName };
}

function resolveUserKey(
  candidate: {
    twitterUserId?: unknown;
    userName?: unknown;
    agentId?: unknown;
  },
  lookups: ReturnType<typeof buildUserLookups>,
): string | null {
  const twitterUserId = normalizeString(candidate.twitterUserId);
  if (twitterUserId && lookups.byTwitterUserId.has(twitterUserId)) return lookups.byTwitterUserId.get(twitterUserId)!;

  const userName = normalizeString(candidate.userName).toLowerCase();
  if (userName && lookups.byUserName.has(userName)) return lookups.byUserName.get(userName)!;

  const agentId = normalizeScalar(candidate.agentId);
  if (agentId && lookups.byAgentId.has(agentId)) return lookups.byAgentId.get(agentId)!;

  if (agentId && agentId.startsWith("user_") && lookups.byAgentId.has(agentId.slice(5))) {
    return lookups.byAgentId.get(agentId.slice(5))!;
  }

  return null;
}

function collectTopicCatalog(raw: RawDataset): string[] {
  const directTopics = raw.topics.flatMap((topicDoc) => safeArray(topicDoc.topics));
  const userTopics = raw.users.flatMap((user) => safeArray(user?.profile?.other_info?.topics));
  return normalizeStringArray([...directTopics, ...userTopics]).slice(0, 48);
}

function buildSourceUserFeatures(raw: RawDataset): SourceUserFeature[] {
  const lookups = buildUserLookups(raw.users);
  const postsByUser = new Map<string, string[]>();
  const repliesByUser = new Map<string, string[]>();

  for (const post of raw.posts) {
    const userKey = resolveUserKey(
      {
        twitterUserId: post.twitter_author_id,
        userName: post.post_user,
        agentId: post.agent_id,
      },
      lookups,
    );
    if (!userKey) continue;
    const bucket = postsByUser.get(userKey) || [];
    const content = normalizeString(post.content);
    if (content) bucket.push(content);
    postsByUser.set(userKey, bucket);
  }

  for (const reply of raw.replies) {
    const userKey = resolveUserKey(
      {
        twitterUserId: reply.twitter_author_id,
        userName: reply.reply_user,
        agentId: reply.re_agent_id,
      },
      lookups,
    );
    if (!userKey) continue;
    const bucket = repliesByUser.get(userKey) || [];
    const content = normalizeString(reply.content);
    if (content) bucket.push(content);
    repliesByUser.set(userKey, bucket);
  }

  return raw.users.map((user) => {
    const userKey = deriveUserKey(user);
    const topics = normalizeStringArray([
      ...safeArray(user?.profile?.other_info?.topics),
      ...safeArray(user.source_topics),
    ]);
    const recentTexts = [...(postsByUser.get(userKey) || []), ...(repliesByUser.get(userKey) || [])].slice(0, 8);
    const description = normalizeString(user.description);
    const country = normalizeString(user?.profile?.other_info?.country) || normalizeString(user.location) || null;
    const userName = normalizeString(user.user_name) || `agent_${normalizeString(user.agent_id) || userKey}`;
    const followersCount =
      toNumber(user.followers_count) ??
      toNumber(user?.public_metrics?.followers_count) ??
      0;
    const activityCount = recentTexts.length;
    const descriptionTokens = tokenize(`${description} ${topics.join(" ")}`);
    const recentTextTokens = tokenize(recentTexts.join(" "));
    const topicTokens = tokenize(topics.join(" "));

    return {
      userKey,
      rawUser: user,
      userName,
      name: normalizeString(user.name) || userName,
      description,
      topics,
      country,
      gender: normalizeString(user?.profile?.other_info?.gender) || null,
      age: toNumber(user?.profile?.other_info?.age),
      mbti: normalizeString(user?.profile?.other_info?.mbti) || null,
      followersCount,
      activityCount,
      recentTexts,
      descriptionTokens,
      recentTextTokens,
      topicTokens,
      userType: normalizeString(user.user_type) || (followersCount >= 20_000 ? "kol" : "normal"),
    };
  });
}

function buildPersonaText(feature: SourceUserFeature, algorithm: string, syntheticVariant: number): string {
  const parts = [
    feature.description || `${feature.name} is an active ${feature.rawUser.recsys_type || "social"} user.`,
    feature.topics.length ? `Focus topics: ${feature.topics.slice(0, 4).join(", ")}.` : "",
    feature.recentTexts.length
      ? `Recent signals: ${feature.recentTexts
          .slice(0, 2)
          .map((text) => text.slice(0, 100))
          .join(" | ")}.`
      : "",
  ].filter(Boolean);

  if (algorithm === "persona-llm") {
    parts.push("Persona is enriched from real profile metadata, recent posts, and reply behavior.");
  }
  if (algorithm === "community-homophily") {
    parts.push("Persona preserves real community signals and prioritizes homophily with triadic closure during graph expansion.");
  }
  if (algorithm === "real-seed-fusion") {
    parts.push("Persona preserves the real seed profile first, then adds minimal graph-fitting enrichment.");
  }
  if (syntheticVariant > 0) {
    parts.push("This is a synthetic expansion agent derived from a real user seed.");
  }
  return parts.join(" ").trim();
}

function expandAgents(
  sourceUsers: SourceUserFeature[],
  dataset: PersonaDatasetManifest,
  algorithm: string,
  agentCount: number,
): GeneratedAgentFeature[] {
  const generated: GeneratedAgentFeature[] = [];
  const total = Math.max(1, agentCount);

  for (let index = 0; index < total; index += 1) {
    const template = sourceUsers[index % sourceUsers.length];
    const syntheticVariant = Math.floor(index / sourceUsers.length);
    const generatedUserName =
      syntheticVariant === 0 ? template.userName : `${template.userName}_sim_${syntheticVariant}`;
    const generatedName =
      syntheticVariant === 0 ? template.name : `${template.name} Sim ${syntheticVariant}`;
    const generatedDescription =
      syntheticVariant === 0
        ? template.description || `${template.name} from ${dataset.recsys_type}`
        : `${template.description || template.name} (synthetic expansion ${syntheticVariant})`;

    generated.push({
      ...template,
      generatedId: index,
      personaText: buildPersonaText(template, algorithm, syntheticVariant),
      syntheticVariant,
      generatedUserName,
      generatedName,
      generatedDescription,
    });
  }

  return generated;
}

function buildGeneratedAgentDocs(
  generated: GeneratedAgentFeature[],
  dataset: PersonaDatasetManifest,
  generationId: string,
  algorithm: string,
): GeneratedAgentDocument[] {
  const createdAt = nowIso();
  return generated.map((feature) => ({
    generation_id: generationId,
    dataset_id: dataset.dataset_id,
    algorithm,
    generated_agent_id: feature.generatedId,
    source_user_key: feature.userKey,
    user_name: feature.generatedUserName,
    name: feature.generatedName,
    description: feature.generatedDescription,
    profile: {
      other_info: {
        user_profile: feature.personaText,
        topics: feature.topics,
        gender: feature.gender,
        age: feature.age,
        mbti: feature.mbti,
        country: feature.country,
      },
    },
    recsys_type: dataset.recsys_type,
    user_type: feature.userType,
    interests: feature.topics,
    metadata: {
      source_followers_count: feature.followersCount,
      source_activity_count: feature.activityCount,
      synthetic_variant: feature.syntheticVariant,
      recent_texts: feature.recentTexts.slice(0, 3),
    },
    created_at: createdAt,
  }));
}

function similarityScore(a: GeneratedAgentFeature, b: GeneratedAgentFeature): number {
  const topicOverlap = setOverlapScore(a.topicTokens, b.topicTokens);
  const descriptionSimilarity = setOverlapScore(a.descriptionTokens, b.descriptionTokens);
  const recentTextSimilarity = setOverlapScore(a.recentTextTokens, b.recentTextTokens);
  const activitySimilarity = normalizedDifferenceScore(a.activityCount, b.activityCount);
  const followersSimilarity = normalizedDifferenceScore(a.followersCount, b.followersCount);

  return (
    topicOverlap * FEATURE_WEIGHTS.topic_overlap +
    descriptionSimilarity * FEATURE_WEIGHTS.description_similarity +
    recentTextSimilarity * FEATURE_WEIGHTS.recent_text_similarity +
    activitySimilarity * FEATURE_WEIGHTS.activity_similarity +
    followersSimilarity * FEATURE_WEIGHTS.followers_similarity
  );
}

function communityKey(feature: GeneratedAgentFeature): string {
  return (
    normalizeString(feature.topics[0]).toLowerCase() ||
    normalizeString(feature.country).toLowerCase() ||
    normalizeString(feature.userType).toLowerCase() ||
    "general"
  );
}

function buildNeighborMap(edges: Array<Record<string, any>>): Map<string, Set<string>> {
  const neighbors = new Map<string, Set<string>>();
  for (const edge of edges) {
    const source = normalizeString(typeof edge.source === "object" ? edge.source?.id : edge.source);
    const target = normalizeString(typeof edge.target === "object" ? edge.target?.id : edge.target);
    if (!source || !target || source === target) continue;
    if (!neighbors.has(source)) neighbors.set(source, new Set());
    if (!neighbors.has(target)) neighbors.set(target, new Set());
    neighbors.get(source)!.add(target);
    neighbors.get(target)!.add(source);
  }
  return neighbors;
}

function countSharedNeighbors(neighbors: Map<string, Set<string>>, source: string, target: string): number {
  const sourceNeighbors = neighbors.get(source);
  const targetNeighbors = neighbors.get(target);
  if (!sourceNeighbors || !targetNeighbors || !sourceNeighbors.size || !targetNeighbors.size) return 0;
  let shared = 0;
  for (const node of sourceNeighbors) {
    if (targetNeighbors.has(node)) shared += 1;
  }
  return shared;
}

function buildAgentComponents(agentNodeIds: string[], edges: Array<Record<string, any>>): string[][] {
  const adjacency = new Map<string, Set<string>>();
  for (const nodeId of agentNodeIds) {
    adjacency.set(nodeId, new Set());
  }

  for (const edge of edges) {
    const source = normalizeString(typeof edge.source === "object" ? edge.source?.id : edge.source);
    const target = normalizeString(typeof edge.target === "object" ? edge.target?.id : edge.target);
    if (!source.startsWith("agent_") || !target.startsWith("agent_")) continue;
    if (!adjacency.has(source) || !adjacency.has(target)) continue;
    adjacency.get(source)!.add(target);
    adjacency.get(target)!.add(source);
  }

  const visited = new Set<string>();
  const components: string[][] = [];

  for (const nodeId of agentNodeIds) {
    if (visited.has(nodeId)) continue;
    const queue = [nodeId];
    const component: string[] = [];
    visited.add(nodeId);

    while (queue.length > 0) {
      const current = queue.shift()!;
      component.push(current);
      for (const neighbor of adjacency.get(current) || []) {
        if (visited.has(neighbor)) continue;
        visited.add(neighbor);
        queue.push(neighbor);
      }
    }

    components.push(component);
  }

  return components.sort((left, right) => right.length - left.length);
}

function addEdge(
  edges: Array<Record<string, any>>,
  edgeKeys: Set<string>,
  params: {
    source: string;
    target: string;
    type: string;
    origin: "real" | "synthetic" | "topic";
    reason: string;
  },
): boolean {
  if (!params.source || !params.target || params.source === params.target) return false;
  const key = `${params.source}|${params.target}|${params.type}`;
  if (edgeKeys.has(key)) return false;
  edgeKeys.add(key);
  edges.push({
    id: `edge_${edgeKeys.size}`,
    ...params,
  });
  return true;
}

function ensureConnectedAgentGraph(
  generated: GeneratedAgentFeature[],
  edges: Array<Record<string, any>>,
  algorithm: string,
): Array<Record<string, any>> {
  const candidateByNodeId = new Map(generated.map((agent) => [`agent_${agent.generatedId}`, agent]));
  const edgeKeys = new Set(edges.map((edge) => `${edge.source}|${edge.target}|${edge.type}`));
  const nodeIds = Array.from(candidateByNodeId.keys());
  const nextEdges = [...edges];
  let components = buildAgentComponents(nodeIds, nextEdges);

  while (components.length > 1) {
    const baseComponent = components[0];
    let bestBridge:
      | {
          source: string;
          target: string;
          score: number;
        }
      | undefined;

    for (let componentIndex = 1; componentIndex < components.length; componentIndex += 1) {
      const targetComponent = components[componentIndex];
      for (const sourceId of baseComponent) {
        for (const targetId of targetComponent) {
          const sourceFeature = candidateByNodeId.get(sourceId);
          const targetFeature = candidateByNodeId.get(targetId);
          if (!sourceFeature || !targetFeature) continue;
          const score =
            similarityScore(sourceFeature, targetFeature) +
            (communityKey(sourceFeature) === communityKey(targetFeature) ? 0.08 : 0);
          if (!bestBridge || score > bestBridge.score) {
            bestBridge = {
              source: sourceId,
              target: targetId,
              score,
            };
          }
        }
      }
    }

    if (!bestBridge) break;
    addEdge(nextEdges, edgeKeys, {
      source: bestBridge.source,
      target: bestBridge.target,
      type: algorithm === "community-homophily" ? "community_homophily" : "synthetic_bridge",
      origin: "synthetic",
      reason: "connectivity-bridge",
    });
    components = buildAgentComponents(nodeIds, nextEdges);
  }

  return nextEdges;
}

function buildRealGraphBackbone(
  raw: RawDataset,
  generated: GeneratedAgentFeature[],
  sourceUsers: SourceUserFeature[],
): {
  edges: Array<Record<string, any>>;
  realEdgeSources: string[];
} {
  const edges: Array<Record<string, any>> = [];
  const edgeKeys = new Set<string>();
  const lookups = buildUserLookups(raw.users);
  const baseAgentIdByUserKey = new Map<string, number>();
  const sourceCount = sourceUsers.length;

  for (let index = 0; index < sourceCount; index += 1) {
    baseAgentIdByUserKey.set(sourceUsers[index].userKey, generated[index].generatedId);
  }

  const realSources = new Set<string>();
  const postAuthorByExternalId = new Map<string, string>();

  for (const post of raw.posts) {
    const authorKey = resolveUserKey(
      {
        twitterUserId: post.twitter_author_id,
        userName: post.post_user,
        agentId: post.agent_id,
      },
      lookups,
    );
    if (!authorKey) continue;
    const postId = normalizeString(post.twitter_post_id) || normalizeString(post.external_id) || normalizeString(post.post_id);
    if (postId) postAuthorByExternalId.set(postId, authorKey);
  }

  for (const relationship of raw.relationships) {
    const sourceUserKey = resolveUserKey(
      {
        userName: relationship.fromUserId,
        agentId: relationship.fromUserId,
      },
      lookups,
    );
    const targetUserKey = resolveUserKey(
      {
        userName: relationship.toUserId,
        agentId: relationship.toUserId,
      },
      lookups,
    );
    if (!sourceUserKey || !targetUserKey) continue;
    const sourceGeneratedId = baseAgentIdByUserKey.get(sourceUserKey);
    const targetGeneratedId = baseAgentIdByUserKey.get(targetUserKey);
    if (sourceGeneratedId == null || targetGeneratedId == null) continue;
    if (
      addEdge(edges, edgeKeys, {
        source: `agent_${sourceGeneratedId}`,
        target: `agent_${targetGeneratedId}`,
        type: normalizeString(relationship.type) || "follow",
        origin: "real",
        reason: "relationships",
      })
    ) {
      realSources.add("relationships");
    }
  }

  for (const network of raw.networks) {
    for (const follow of safeArray<Record<string, any>>(network.follows)) {
      const sourceUserKey = resolveUserKey(
        {
          userName: follow.fromUserId,
          agentId: follow.fromUserId,
        },
        lookups,
      );
      const targetUserKey = resolveUserKey(
        {
          userName: follow.toUserId,
          agentId: follow.toUserId,
        },
        lookups,
      );
      if (!sourceUserKey || !targetUserKey) continue;
      const sourceGeneratedId = baseAgentIdByUserKey.get(sourceUserKey);
      const targetGeneratedId = baseAgentIdByUserKey.get(targetUserKey);
      if (sourceGeneratedId == null || targetGeneratedId == null) continue;
      if (
        addEdge(edges, edgeKeys, {
          source: `agent_${sourceGeneratedId}`,
          target: `agent_${targetGeneratedId}`,
          type: "follow",
          origin: "real",
          reason: "networks",
        })
      ) {
        realSources.add("networks");
      }
    }
  }

  for (const reply of raw.replies) {
    const sourceUserKey = resolveUserKey(
      {
        twitterUserId: reply.twitter_author_id,
        userName: reply.reply_user,
        agentId: reply.re_agent_id,
      },
      lookups,
    );
    const postKey =
      postAuthorByExternalId.get(normalizeString(reply.twitter_post_id)) ||
      postAuthorByExternalId.get(normalizeString(reply.post_id)) ||
      resolveUserKey(
        {
          twitterUserId: reply.twitter_reply_to_user_id,
          userName: reply.post_user,
        },
        lookups,
    );
    if (!sourceUserKey || !postKey) continue;
    const sourceGeneratedId = baseAgentIdByUserKey.get(sourceUserKey);
    const targetGeneratedId = baseAgentIdByUserKey.get(postKey);
    if (sourceGeneratedId == null || targetGeneratedId == null) continue;
    if (
      addEdge(edges, edgeKeys, {
        source: `agent_${sourceGeneratedId}`,
        target: `agent_${targetGeneratedId}`,
        type: "interaction",
        origin: "real",
        reason: "replies",
      })
    ) {
      realSources.add("replies");
    }
  }

  for (const doc of [...raw.posts, ...raw.replies]) {
    const content = normalizeString(doc.content);
    if (!content) continue;
    const sourceUserKey = resolveUserKey(
      {
        twitterUserId: doc.twitter_author_id,
        userName: doc.post_user || doc.reply_user,
        agentId: doc.agent_id || doc.re_agent_id,
      },
      lookups,
    );
    if (!sourceUserKey) continue;
    const mentions = Array.from(content.matchAll(/@([A-Za-z0-9_]{2,32})/g)).map((match) => match[1].toLowerCase());
    for (const mention of mentions) {
      const targetUserKey = lookups.byUserName.get(mention);
      if (!targetUserKey) continue;
      const sourceGeneratedId = baseAgentIdByUserKey.get(sourceUserKey);
      const targetGeneratedId = baseAgentIdByUserKey.get(targetUserKey);
      if (sourceGeneratedId == null || targetGeneratedId == null) continue;
      if (
        addEdge(edges, edgeKeys, {
          source: `agent_${sourceGeneratedId}`,
          target: `agent_${targetGeneratedId}`,
          type: "interaction",
          origin: "real",
          reason: "mentions",
        })
      ) {
        realSources.add("mentions");
      }
    }
  }

  return {
    edges,
    realEdgeSources: Array.from(realSources),
  };
}

function buildSyntheticEdges(
  generated: GeneratedAgentFeature[],
  existingEdges: Array<Record<string, any>>,
  algorithm: string,
): Array<Record<string, any>> {
  const edges = [...existingEdges];
  const edgeKeys = new Set(edges.map((edge) => `${edge.source}|${edge.target}|${edge.type}`));
  const degree = new Map<string, number>();
  for (const agent of generated) {
    degree.set(`agent_${agent.generatedId}`, 0);
  }
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
  }

  const minDegree = algorithm === "ba-structural" ? 1 : 2;
  const targetSyntheticEdges = Math.max(generated.length, Math.ceil(generated.length * 1.5));

  const candidates = generated.map((agent) => ({
    ...agent,
    nodeId: `agent_${agent.generatedId}`,
  }));

  if (algorithm === "community-homophily") {
    const targetAverageDegree =
      existingEdges.length > 0
        ? Math.min(4.2, Math.max(2.4, (existingEdges.length * 2) / Math.max(generated.length, 1) + 0.8))
        : 2.8;
    const targetTotalEdges = Math.max(existingEdges.length + 1, Math.ceil((generated.length * targetAverageDegree) / 2));
    const communities = new Map<string, Array<(typeof candidates)[number]>>();
    const neighborMap = buildNeighborMap(edges);

    const registerEdge = (
      source: string,
      target: string,
      reason: string,
      type = "community_homophily",
    ) => {
      const added = addEdge(edges, edgeKeys, {
        source,
        target,
        type,
        origin: "synthetic",
        reason,
      });
      if (!added) return false;
      degree.set(source, (degree.get(source) || 0) + 1);
      degree.set(target, (degree.get(target) || 0) + 1);
      if (!neighborMap.has(source)) neighborMap.set(source, new Set());
      if (!neighborMap.has(target)) neighborMap.set(target, new Set());
      neighborMap.get(source)!.add(target);
      neighborMap.get(target)!.add(source);
      return true;
    };

    for (const candidate of candidates) {
      const key = communityKey(candidate);
      const bucket = communities.get(key) || [];
      bucket.push(candidate);
      communities.set(key, bucket);
    }

    for (const members of [...communities.values()].sort((left, right) => right.length - left.length)) {
      if (edges.length >= targetTotalEdges) break;
      const ranked = [...members].sort(
        (left, right) =>
          right.followersCount +
          right.activityCount * 30 +
          (degree.get(right.nodeId) || 0) * 20 -
          (left.followersCount + left.activityCount * 30 + (degree.get(left.nodeId) || 0) * 20),
      );
      const anchors = ranked.slice(0, Math.min(2, ranked.length));
      for (const member of ranked) {
        if (edges.length >= targetTotalEdges) break;
        if ((degree.get(member.nodeId) || 0) >= 1) continue;
        const bestAnchor = anchors
          .filter((anchor) => anchor.nodeId !== member.nodeId)
          .map((anchor) => ({
            anchor,
            score: similarityScore(member, anchor),
          }))
          .sort((left, right) => right.score - left.score)[0]?.anchor;
        if (!bestAnchor) continue;
        registerEdge(member.nodeId, bestAnchor.nodeId, "community-anchor");
      }
    }

    for (const agent of [...candidates].sort((left, right) => (degree.get(left.nodeId) || 0) - (degree.get(right.nodeId) || 0))) {
      if (edges.length >= targetTotalEdges) break;
      if ((degree.get(agent.nodeId) || 0) >= 2) continue;

      const rankedCandidates = candidates
        .filter((candidate) => candidate.nodeId !== agent.nodeId && communityKey(candidate) === communityKey(agent))
        .map((candidate) => {
          const similarity = similarityScore(agent, candidate);
          const sharedNeighbors = countSharedNeighbors(neighborMap, agent.nodeId, candidate.nodeId);
          return {
            candidate,
            score: sharedNeighbors * 0.45 + similarity * 0.55,
            sharedNeighbors,
            similarity,
          };
        })
        .sort((left, right) => right.score - left.score);

      for (const item of rankedCandidates) {
        if (item.sharedNeighbors < 1 && item.similarity < 0.14) continue;
        const added = registerEdge(agent.nodeId, item.candidate.nodeId, item.sharedNeighbors > 0 ? "triadic-closure" : "assortative-mixing");
        if (added) break;
      }
    }

    const communityAnchors = [...communities.values()]
      .map((members) =>
        [...members].sort(
          (left, right) => right.followersCount + right.activityCount * 30 - (left.followersCount + left.activityCount * 30),
        )[0],
      )
      .filter(Boolean);

    const maxBridgeEdges = Math.max(1, Math.ceil(communityAnchors.length / 2));
    let bridgeEdges = 0;
    for (let i = 0; i < communityAnchors.length; i += 1) {
      if (edges.length >= targetTotalEdges || bridgeEdges >= maxBridgeEdges) break;
      const source = communityAnchors[i];
      const bestBridge = communityAnchors
        .filter((target) => target.nodeId !== source.nodeId && communityKey(target) !== communityKey(source))
        .map((target) => ({
          target,
          score: similarityScore(source, target),
        }))
        .sort((left, right) => right.score - left.score)[0];
      if (!bestBridge || bestBridge.score < 0.08) continue;
      if (registerEdge(source.nodeId, bestBridge.target.nodeId, "community-bridge")) {
        bridgeEdges += 1;
      }
    }

    for (const agent of [...candidates].sort((left, right) => (degree.get(left.nodeId) || 0) - (degree.get(right.nodeId) || 0))) {
      if (edges.length >= targetTotalEdges) break;
      if ((degree.get(agent.nodeId) || 0) >= 2) continue;
      const fallback = candidates
        .filter((candidate) => candidate.nodeId !== agent.nodeId)
        .map((candidate) => ({
          candidate,
          score: similarityScore(agent, candidate),
        }))
        .sort((left, right) => right.score - left.score)[0];
      if (!fallback || fallback.score < 0.12) continue;
      registerEdge(agent.nodeId, fallback.candidate.nodeId, "assortative-mixing");
    }

    return edges;
  }

  if (algorithm === "real-seed-fusion") {
    const desiredSyntheticEdges = Math.max(1, Math.ceil(generated.length * 0.7));
    const targetTotalEdges = existingEdges.length + desiredSyntheticEdges;
    const anchorCount = Math.min(6, Math.max(2, Math.ceil(generated.length * 0.15)));
    const anchors = [...candidates]
      .sort(
        (left, right) =>
          right.followersCount + right.activityCount * 30 - (left.followersCount + left.activityCount * 30),
      )
      .slice(0, anchorCount);

    const rankedSimilarity = (agent: (typeof candidates)[number]) =>
      candidates
        .filter((candidate) => candidate.nodeId !== agent.nodeId)
        .map((candidate) => ({
          candidate,
          score: similarityScore(agent, candidate),
          topicOverlap: setOverlapScore(agent.topicTokens, candidate.topicTokens),
          textOverlap: setOverlapScore(agent.recentTextTokens, candidate.recentTextTokens),
        }))
        .sort((left, right) => right.score - left.score);

    for (const agent of [...candidates].sort((left, right) => (degree.get(left.nodeId) || 0) - (degree.get(right.nodeId) || 0))) {
      if (edges.length >= targetTotalEdges) break;
      if ((degree.get(agent.nodeId) || 0) >= 1) continue;

      const bestAnchor = anchors
        .filter((candidate) => candidate.nodeId !== agent.nodeId)
        .map((candidate) => ({
          candidate,
          score: similarityScore(agent, candidate),
        }))
        .sort((left, right) => right.score - left.score)[0];

      const anchorTarget = bestAnchor?.candidate || anchors.find((candidate) => candidate.nodeId !== agent.nodeId);
      if (!anchorTarget) continue;

      const added = addEdge(edges, edgeKeys, {
        source: agent.nodeId,
        target: anchorTarget.nodeId,
        type: "seed_fusion",
        origin: "synthetic",
        reason: "real-priority-anchor",
      });
      if (added) {
        degree.set(agent.nodeId, (degree.get(agent.nodeId) || 0) + 1);
        degree.set(anchorTarget.nodeId, (degree.get(anchorTarget.nodeId) || 0) + 1);
      }
    }

    const topicGroups = new Map<string, Array<(typeof candidates)[number]>>();
    for (const candidate of candidates) {
      for (const topic of candidate.topics.slice(0, 3)) {
        const bucket = topicGroups.get(topic) || [];
        bucket.push(candidate);
        topicGroups.set(topic, bucket);
      }
    }

    for (const [, members] of [...topicGroups.entries()].sort((left, right) => right[1].length - left[1].length)) {
      if (edges.length >= targetTotalEdges) break;
      const rankedMembers = [...members].sort(
        (left, right) =>
          right.followersCount + right.activityCount * 30 - (left.followersCount + left.activityCount * 30),
      );
      for (let index = 1; index < rankedMembers.length; index += 1) {
        const source = rankedMembers[index];
        const target = rankedMembers[index - 1];
        if ((degree.get(source.nodeId) || 0) >= 2) continue;
        const added = addEdge(edges, edgeKeys, {
          source: source.nodeId,
          target: target.nodeId,
          type: "seed_fusion",
          origin: "synthetic",
          reason: "topic-cluster-bridge",
        });
        if (added) {
          degree.set(source.nodeId, (degree.get(source.nodeId) || 0) + 1);
          degree.set(target.nodeId, (degree.get(target.nodeId) || 0) + 1);
        }
        if (edges.length >= targetTotalEdges) break;
      }
    }

    for (const agent of [...candidates].sort((left, right) => (degree.get(left.nodeId) || 0) - (degree.get(right.nodeId) || 0))) {
      if (edges.length >= targetTotalEdges) break;
      if ((degree.get(agent.nodeId) || 0) >= 2) continue;

      for (const { candidate, score, topicOverlap, textOverlap } of rankedSimilarity(agent)) {
        if (score < 0.14) continue;
        if (topicOverlap <= 0 && textOverlap <= 0.08) continue;
        const added = addEdge(edges, edgeKeys, {
          source: agent.nodeId,
          target: candidate.nodeId,
          type: "seed_fusion",
          origin: "synthetic",
          reason: "real-priority-homophily",
        });
        if (!added) continue;
        degree.set(agent.nodeId, (degree.get(agent.nodeId) || 0) + 1);
        degree.set(candidate.nodeId, (degree.get(candidate.nodeId) || 0) + 1);
        break;
      }
    }

    return edges;
  }

  if (algorithm === "ba-structural") {
    const rankedByDegree = () =>
      [...candidates].sort((left, right) => (degree.get(right.nodeId) || 0) - (degree.get(left.nodeId) || 0));

    for (const agent of candidates.sort((left, right) => (degree.get(left.nodeId) || 0) - (degree.get(right.nodeId) || 0))) {
      if ((degree.get(agent.nodeId) || 0) >= minDegree) continue;
      for (const candidate of rankedByDegree()) {
        if (candidate.nodeId === agent.nodeId) continue;
        const added = addEdge(edges, edgeKeys, {
          source: agent.nodeId,
          target: candidate.nodeId,
          type: "synthetic_follow",
          origin: "synthetic",
          reason: "preferential-attachment",
        });
        if (added) {
          degree.set(agent.nodeId, (degree.get(agent.nodeId) || 0) + 1);
          degree.set(candidate.nodeId, (degree.get(candidate.nodeId) || 0) + 1);
        }
        if ((degree.get(agent.nodeId) || 0) >= minDegree) break;
      }
    }
    return edges;
  }

  for (const agent of candidates) {
    const nodeId = agent.nodeId;
    const scoredCandidates = candidates
      .filter((candidate) => candidate.nodeId !== nodeId)
      .map((candidate) => ({
        candidate,
        score: similarityScore(agent, candidate),
      }))
      .sort((left, right) => right.score - left.score);

    const desiredLinks = (degree.get(nodeId) || 0) >= minDegree ? 1 : 2;
    let addedLinks = 0;

    for (const { candidate, score } of scoredCandidates) {
      if (score <= 0.08) continue;
      const added = addEdge(edges, edgeKeys, {
        source: nodeId,
        target: candidate.nodeId,
        type: "homophily",
        origin: "synthetic",
        reason: "semantic-homophily",
      });
      if (!added) continue;
      degree.set(nodeId, (degree.get(nodeId) || 0) + 1);
      degree.set(candidate.nodeId, (degree.get(candidate.nodeId) || 0) + 1);
      addedLinks += 1;
      if (addedLinks >= desiredLinks) break;
      if (edges.length >= targetSyntheticEdges + existingEdges.length) break;
    }
  }

  return edges;
}

function buildTopicNodesAndEdges(
  generatedAgents: GeneratedAgentDocument[],
  graphEdges: Array<Record<string, any>>,
): { nodes: Array<Record<string, any>>; edges: Array<Record<string, any>> } {
  const topicCounts = new Map<string, number>();
  for (const agent of generatedAgents) {
    for (const topic of agent.interests) {
      topicCounts.set(topic, (topicCounts.get(topic) || 0) + 1);
    }
  }

  const topicNodes = Array.from(topicCounts.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, 12)
    .map(([topic, count], index) => ({
      id: `topic_${index}`,
      type: "topic",
      name: topic,
      heat: count,
      source: "persona-dataset",
    }));

  const topicIdByName = new Map(topicNodes.map((node) => [node.name, node.id]));
  const edgeKeys = new Set(graphEdges.map((edge) => `${edge.source}|${edge.target}|${edge.type}`));
  const edges = [...graphEdges];

  for (const agent of generatedAgents) {
    for (const topic of agent.interests.slice(0, 3)) {
      const topicNodeId = topicIdByName.get(topic);
      if (!topicNodeId) continue;
      addEdge(edges, edgeKeys, {
        source: `agent_${agent.generated_agent_id}`,
        target: topicNodeId,
        type: "topic_link",
        origin: "topic",
        reason: "topic-membership",
      });
    }
  }

  return { nodes: topicNodes, edges };
}

function buildGraphStats(nodes: Array<Record<string, any>>, edges: Array<Record<string, any>>, generatedAgents: GeneratedAgentDocument[]) {
  const agentCount = generatedAgents.length;
  const topicCount = nodes.filter((node) => node.type === "topic").length;
  const realEdgeCount = edges.filter((edge) => edge.origin === "real").length;
  const syntheticEdgeCount = edges.filter((edge) => edge.origin === "synthetic").length;
  const agentOnlyEdges = edges.filter((edge) => edge.source.startsWith("agent_") && edge.target.startsWith("agent_")).length;
  const density = agentCount > 1 ? agentOnlyEdges / (agentCount * (agentCount - 1)) : 0;

  return {
    nodeCount: nodes.length,
    edgeCount: edges.length,
    density: Number(density.toFixed(4)),
    agentCount,
    topicCount,
    realEdgeCount,
    syntheticEdgeCount,
  };
}

function buildAlgorithmExplanation(params: {
  algorithm: string;
  realEdgeSources: string[];
}): GeneratedGraphDocument["algorithm_explanation"] {
  const { algorithm, realEdgeSources } = params;
  const personaMode =
    algorithm === "persona-llm"
      ? "heuristic_real_profile_enrichment"
      : algorithm === "community-homophily"
        ? "community_homophily_enrichment"
      : algorithm === "real-seed-fusion"
        ? "real_seed_priority_enrichment"
        : "template_real_profile_enrichment";
  const syntheticEdgeRules: SyntheticRule[] =
    algorithm === "community-homophily"
      ? [
          {
            rule: "community-anchor",
            trigger: "Applied when a topic community has sparse or isolated nodes after importing real edges.",
            description: "Attach low-degree users to stronger in-community anchors before broader synthetic expansion.",
          },
          {
            rule: "triadic-closure",
            trigger: "Applied when two users share neighbors or reply neighborhoods but remain disconnected.",
            description: "Close likely triangles inside the same community to improve local clustering and graph readability.",
          },
          {
            rule: "community-bridge",
            trigger: "Applied when separate topic communities need a small number of bridge links for overall connectivity.",
            description: "Add limited cross-community links between anchor users with compatible content signals.",
          },
          {
            rule: "connectivity-bridge",
            trigger: "Applied when the agent graph still has multiple disconnected components after community expansion.",
            description: "Add the minimum number of synthetic bridges needed to keep the main agent graph connected.",
          },
        ]
      : algorithm === "ba-structural"
      ? [
          {
            rule: "preferential-attachment",
            trigger: "Applied when real graph is sparse or isolated nodes remain after real-edge import.",
            description: "Attach low-degree nodes to higher-degree nodes to preserve a readable network backbone.",
          },
        ]
      : algorithm === "real-seed-fusion"
        ? [
            {
              rule: "real-priority-anchor",
              trigger: "Applied when real edges leave isolated users after reply/mention/relationship import.",
              description: "Connect sparse nodes to active or influential real seed anchors before adding broader synthetic links.",
            },
            {
              rule: "topic-cluster-bridge",
              trigger: "Applied when users share dominant topics but remain weakly connected.",
              description: "Bridge topic clusters with minimal extra edges so the graph stays readable without over-synthesizing structure.",
            },
          ]
      : [
          {
            rule: "semantic-homophily",
            trigger: "Applied when real graph is sparse or node degree is below the target threshold.",
            description: "Use topic overlap, profile text, recent text, activity, and followers similarity to add synthetic links.",
          },
        ];

  return {
    algorithm,
    version: PERSONA_VERSION,
    real_edge_sources: realEdgeSources,
    synthetic_edge_rules: syntheticEdgeRules,
    feature_weights: FEATURE_WEIGHTS,
    persona_enrichment_mode: personaMode,
  };
}

export function buildGeneratedArtifacts(params: {
  dataset: PersonaDatasetManifest;
  raw: RawDataset;
  options?: GenerationOptions;
}): GenerationBuildResult {
  const { dataset, raw, options } = params;
  const sourceUsers = buildSourceUserFeatures(raw);
  if (sourceUsers.length === 0) {
    throw new Error("数据集中没有可用于生成的 users 数据");
  }

  const algorithm = normalizeString(options?.algorithm) || "community-homophily";
  const requestedAgentCount = options?.agentCount && options.agentCount > 0 ? Math.floor(options.agentCount) : sourceUsers.length;
  const generatedFeatures = expandAgents(sourceUsers, dataset, algorithm, requestedAgentCount);
  const generationId = createGenerationId();
  const generatedAgents = buildGeneratedAgentDocs(generatedFeatures, dataset, generationId, algorithm);

  const realBackbone = buildRealGraphBackbone(raw, generatedFeatures, sourceUsers);
  const withSyntheticEdges = buildSyntheticEdges(generatedFeatures, realBackbone.edges, algorithm);
  const connectedEdges = ensureConnectedAgentGraph(generatedFeatures, withSyntheticEdges, algorithm);
  const agentNodes = generatedAgents.map((agent) => ({
    id: `agent_${agent.generated_agent_id}`,
    type: "agent",
    name: agent.name,
    bio: agent.profile.other_info.user_profile,
    interests: agent.interests,
    userType: agent.user_type,
    sourceUserKey: agent.source_user_key,
  }));
  const topicGraph = buildTopicNodesAndEdges(generatedAgents, connectedEdges);
  const nodes = [...agentNodes, ...topicGraph.nodes];
  const edges = topicGraph.edges;

  const graphDocument: GeneratedGraphDocument = {
    generation_id: generationId,
    dataset_id: dataset.dataset_id,
    algorithm,
    nodes,
    edges,
    stats: buildGraphStats(nodes, edges, generatedAgents),
    algorithm_explanation: buildAlgorithmExplanation({
      algorithm,
      realEdgeSources: realBackbone.realEdgeSources,
    }),
    created_at: nowIso(),
  };

  return {
    generationId,
    generatedAgents,
    graphDocument,
  };
}

export function buildGenerationCounts(agents: GeneratedAgentDocument[], graph: GeneratedGraphDocument): DatasetCounts {
  return {
    users: agents.length,
    posts: 0,
    replies: 0,
    relationships: graph.edges.filter((edge) => edge.origin === "real").length,
    networks: graph.edges.filter((edge) => edge.origin === "synthetic").length,
    topics: graph.stats.topicCount,
  };
}
