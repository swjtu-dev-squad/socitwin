/** 用户画像页（旧 oasis-dashboard）专用类型，与 /api/persona 响应对齐 */

export type AvailabilityStatus = 'collected' | 'not_collected' | 'unsupported' | 'failed';

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

export interface PersonaDatasetSummary {
  dataset_id: string;
  label: string;
  recsys_type: string;
  source: string;
  status: 'ready' | 'partial' | 'failed';
  ingest_status: string;
  counts: DatasetCounts;
  availability: DatasetAvailability;
  latest_generation_id?: string | null;
  created_at: string;
  updated_at: string;
  meta?: Record<string, unknown>;
}

export interface PersonaGenerationExplanation {
  algorithm: string;
  version: string;
  real_edge_sources: string[];
  synthetic_edge_rules: Array<{
    rule: string;
    trigger: string;
    description: string;
  }>;
  feature_weights: {
    topic_overlap: number;
    description_similarity: number;
    recent_text_similarity: number;
    activity_similarity: number;
    followers_similarity: number;
  };
  persona_enrichment_mode: string;
}

export interface GeneratedAgentRecord {
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
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface PersonaRawDataResponse<T = Record<string, unknown>> {
  dataset_id: string;
  type: string;
  stats: {
    count: number;
    page: number;
    pageSize: number;
    totalPages: number;
  };
  data: T[];
}

export interface GeneratedGraphRecord {
  generation_id: string;
  dataset_id: string;
  algorithm: string;
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  stats: {
    nodeCount: number;
    edgeCount: number;
    density: number;
    agentCount: number;
    topicCount: number;
    realEdgeCount: number;
    syntheticEdgeCount: number;
  };
  algorithm_explanation: PersonaGenerationExplanation;
  created_at: string;
}
