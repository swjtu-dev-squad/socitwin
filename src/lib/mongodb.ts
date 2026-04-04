import { MongoClient, Db, Collection } from "mongodb";

let client: MongoClient | null = null;
let db: Db | null = null;

export async function connectMongoDB(): Promise<Db> {
  if (db) return db;

  const uri = process.env.MONGODB_URI;
  const database = process.env.MONGODB_DATABASE || "oasis_dataset";

  if (!uri) {
    throw new Error("MONGODB_URI is not set in environment variables");
  }

  try {
    client = new MongoClient(uri);
    await client.connect();
    db = client.db(database);
    console.log(`✅ MongoDB connected: ${database}`);
    return db;
  } catch (error) {
    console.error("❌ MongoDB connection failed:", error);
    throw error;
  }
}

export function getDB(): Db {
  if (!db) {
    throw new Error("MongoDB not connected. Call connectMongoDB() first.");
  }
  return db;
}

export function getCollection(name: string): Collection {
  return getDB().collection(name);
}

// Collection names
export const COLLECTIONS = {
  USERS: "users",
  POSTS: "posts",
  REPLIES: "replies",
  RELATIONSHIPS: "relationships",
  NETWORKS: "networks",
  TOPICS: "topics",
  PERSONA_DATASETS: "persona_datasets",
  GENERATED_AGENTS: "generated_agents",
  GENERATED_GRAPHS: "generated_graphs",
} as const;

export type CollectionType = (typeof COLLECTIONS)[keyof typeof COLLECTIONS];

// Data types for import
export type ImportType = "users" | "posts" | "replies" | "relationships" | "networks" | "topics";

// Get collection name by type
export function getCollectionName(type: ImportType): string {
  const mapping: Record<ImportType, string> = {
    users: COLLECTIONS.USERS,
    posts: COLLECTIONS.POSTS,
    replies: COLLECTIONS.REPLIES,
    relationships: COLLECTIONS.RELATIONSHIPS,
    networks: COLLECTIONS.NETWORKS,
    topics: COLLECTIONS.TOPICS,
  };
  return mapping[type];
}

// Close connection
export async function closeMongoDB(): Promise<void> {
  if (client) {
    await client.close();
    client = null;
    db = null;
    console.log("MongoDB disconnected");
  }
}
