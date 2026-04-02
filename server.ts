import express from "express";
import { createServer } from "http";
import multer from "multer";
import { existsSync, mkdirSync, createWriteStream } from "fs";
import { Server } from "socket.io";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";
import { watch } from "fs";
import Database from "better-sqlite3";
import dotenv from "dotenv";
import {
  connectMongoDB,
  getCollection,
  getCollectionName,
  COLLECTIONS,
  closeMongoDB,
} from "./src/lib/mongodb";

// 🆕 创建日志文件（带时间戳）
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const logDir = path.join(__dirname, 'logs');
if (!existsSync(logDir)) {
  mkdirSync(logDir, { recursive: true });
}

const logFilePath = path.join(logDir, `oasis_engine_${new Date().toISOString().replace(/[:.]/g, '-')}.log`);
const logStream = createWriteStream(logFilePath, { flags: 'a' });

// 🆕 打印日志文件路径
console.log(`📝 OASIS Engine log file: ${logFilePath}`);

function logWithTimestamp(message: string) {
  const timestamp = new Date().toISOString();
  const logLine = `[${timestamp}] ${message}\n`;

  // 写入日志文件
  logStream.write(logLine);

  // 同时打印到控制台
  console.log(message);
}

// Load environment variables from .env file
dotenv.config();

// Python OASIS Engine Process
let oasisProcess: any = null;
let oasisReady = false;
let restartTimeout: NodeJS.Timeout | null = null;
let ioInstance: any = null;

function startOasisEngine() {
  logWithTimestamp("Starting OASIS Engine...");
  oasisProcess = spawn(path.join(__dirname, ".venv", "bin", "python"), [path.join(__dirname, "oasis_dashboard", "real_oasis_engine_v3.py"), "--rpc"], {
    stdio: ["pipe", "pipe", "pipe"],
    env: {
      ...process.env,
      // Explicitly forward all model-related env vars to Python subprocess
      OASIS_MODEL_PLATFORM: process.env.OASIS_MODEL_PLATFORM ?? "openai",
      OASIS_MODEL_TYPE: process.env.OASIS_MODEL_TYPE ?? "gpt-4.1-mini",
      OASIS_MODEL_API_KEY: process.env.OASIS_MODEL_API_KEY ?? process.env.OPENAI_API_KEY ?? "",
      OASIS_MODEL_URL: process.env.OASIS_MODEL_URL ?? process.env.OPENAI_BASE_URL ?? "",
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
      OPENAI_BASE_URL: process.env.OPENAI_BASE_URL ?? "",
      // 🆕 Agent sampling configuration environment variables (Issue #52)
      OASIS_SAMPLING_ENABLED: process.env.OASIS_SAMPLING_ENABLED ?? "false",
      OASIS_SAMPLING_RATE: process.env.OASIS_SAMPLING_RATE ?? "0.1",
      OASIS_SAMPLING_STRATEGY: process.env.OASIS_SAMPLING_STRATEGY ?? "random",
      OASIS_SAMPLING_MIN_ACTIVE: process.env.OASIS_SAMPLING_MIN_ACTIVE ?? "5",
      OASIS_SAMPLING_SEED: process.env.OASIS_SAMPLING_SEED ?? "42",
    },
  });

  oasisProcess.stdout.on("data", (data: Buffer) => {
    const output = data.toString();
    logWithTimestamp(`[OASIS Engine stdout] ${output.trim()}`);
    // Check for ready signal from JSON-RPC server
    if (output.includes('"status":"ready"') || output.includes("ready")) {
      oasisReady = true;
      logWithTimestamp("✅ OASIS Engine ready!");
    }
  });

  oasisProcess.stderr.on("data", (data: Buffer) => {
    const output = data.toString();

    // 🆕 打印所有Python stderr输出（用于DEBUG）
    logWithTimestamp(`[OASIS Engine stderr] ${output.trim()}`);

    // 解析进度信息
    const progressMatch = output.match(/📊 Progress: (\d+)\/(\d+) \((\d+)%\)/);
    if (progressMatch && ioInstance) {
      const [, current, total, percentage] = progressMatch;
      ioInstance.emit("step_progress", {
        current: parseInt(current),
        total: parseInt(total),
        percentage: parseInt(percentage),
      });
    }

    // 解析完成信号
    if (output.includes("✅ Step complete") && ioInstance) {
      ioInstance.emit("step_complete");
    }

    // 智能分类输出类型
    if (output.toLowerCase().includes("warning")) {
      console.warn(`\x1b[33m[OASIS Engine Warning]\x1b[0m ${output.trim()}`);
    } else if (output.includes("✅") || output.toLowerCase().includes("ready") || output.toLowerCase().includes("成功") || output.toLowerCase().includes("已启动")) {
      console.log(`\x1b[36m[OASIS Engine]\x1b[0m ${output.trim()}`);
    } else if (output.toLowerCase().includes("error") || output.toLowerCase().includes("exception") || output.toLowerCase().includes("failed")) {
      console.error(`\x1b[31m[OASIS Engine Error]\x1b[0m ${output.trim()}`);
    } else {
      console.log(`\x1b[90m[OASIS Engine Info]\x1b[0m ${output.trim()}`);
    }
  });

  oasisProcess.on("close", (code: number) => {
    console.log(`OASIS Engine process exited with code ${code}`);
    oasisReady = false;
  });
}

function restartOasisEngine() {
  console.log("\x1b[35m🔄 Restarting OASIS Engine due to Python file changes...\x1b[0m");

  // 清除之前的重启定时器
  if (restartTimeout) {
    clearTimeout(restartTimeout);
  }

  // 防抖：1秒后重启，避免频繁重启
  restartTimeout = setTimeout(() => {
    if (oasisProcess) {
      oasisProcess.kill();
    }
    oasisReady = false;
    startOasisEngine();
  }, 1000);
}

function watchPythonFiles() {
  const pythonDir = path.join(__dirname, "oasis_dashboard");

  if (!existsSync(pythonDir)) {
    console.warn(`[Python Watch] Directory not found: ${pythonDir}`);
    return;
  }

  console.log(`\x1b[35m🐍 Watching Python files in: ${pythonDir}\x1b[0m`);

  // 监听整个oasis_dashboard目录
  watch(pythonDir, { recursive: true }, (eventType, filename) => {
    if (filename && filename.endsWith('.py')) {
      console.log(`\x1b[35m[Python Watch] Detected change in: ${filename}\x1b[0m`);
      restartOasisEngine();
    }
  });
}

async function callOasisEngine(method: string, params: any = {}): Promise<any> {
  return new Promise((resolve, reject) => {
    if (!oasisProcess || !oasisReady) {
      reject(new Error("OASIS Engine not ready"));
      return;
    }

    // 🆕 DEBUG: 打印请求参数
    logWithTimestamp(`[JSON-RPC] Sending ${method} request`);
    logWithTimestamp(`[JSON-RPC] params keys: ${Object.keys(params).join(', ')}`);
    if (method === "initialize") {
      logWithTimestamp(`[JSON-RPC] sampling_config: ${JSON.stringify(params.sampling_config)}`);
    }

    const request = {
      jsonrpc: "2.0",
      method: method,
      params: params,
      id: Date.now(),
    };

    let buffer = "";
    
    const dataHandler = (data: Buffer) => {
      buffer += data.toString();
      const lines = buffer.split("\n");
      
      // Keep the last incomplete line in buffer
      buffer = lines.pop() || "";
      
      // Process each complete line
      for (const line of lines) {
        if (!line.trim()) continue;
        
        try {
          const response = JSON.parse(line);
          // Check if this is a JSON-RPC response (not a status message)
          if (response.jsonrpc === "2.0" && response.id === request.id) {
            oasisProcess.stdout.removeListener("data", dataHandler);
            if (response.error) {
              reject(new Error(response.error.message));
            } else {
              resolve(response.result);
            }
            return;
          }
        } catch (e) {
          // Not a JSON line, skip it
        }
      }
    };

    oasisProcess.stdout.on("data", dataHandler);
    oasisProcess.stdin.write(JSON.stringify(request) + "\n");

    setTimeout(() => {
      oasisProcess.stdout.removeListener("data", dataHandler);
      reject(new Error("OASIS Engine timeout"));
    }, 300000); // 300 seconds (5 minutes) timeout - supports large-scale simulations
  });
}

async function startServer() {
  const app = express();
  const httpServer = createServer(app);
  const io = new Server(httpServer, {
    cors: {
      origin: "*",
    },
  });

  // Store io instance globally for use in OASIS engine
  ioInstance = io;

  const PORT = 3000;

  app.use(express.json());

  // Initialize MongoDB connection
  try {
    await connectMongoDB();
  } catch (error) {
    console.error("⚠️ MongoDB connection failed, dataset APIs will not work:", error);
  }

  // Start OASIS Engine (uses ioInstance for progress updates)
  startOasisEngine();

  // Watch Python files for hot reload
  watchPythonFiles();

  // Simulation State (cached from OASIS)
  let simulationState = {
    running: false,
    paused: false,
    currentStep: 0,
    currentRound: 0 as number | null,     // 🆕 OASIS: Current round number
    activeAgents: 0,
    totalPosts: 0,
    polarization: 0.0,
    propagation: null as any,             // 🆕 OASIS: Information propagation metrics
    roundComparison: null as any,         // 🆕 OASIS: Group polarization round comparison
    herdEffect: null as any,              // 🆕 OASIS: Herd effect (Reddit hot score)
    velocity: 0.0,                        // ⚠️ Deprecated: Replaced by propagation
    herdHhi: 0.0,                         // ⚠️ Deprecated: Replaced by herdEffect
    agents: [] as any[],
    platform: "Reddit",
    recsys: "Hot-score",
    topics: [] as string[],
    regions: [] as string[],
    initializationPhase: false as boolean,
    initializationComplete: false as boolean,
    oasis_ready: false as boolean,
  };

  // API Routes - All calling real OASIS Engine

  app.post("/api/sim/config", async (req, res) => {
    try {
      const { agentCount, platform, recsys, topics, regions, topic, region, seedPosts, samplingConfig, sampling_config } = req.body;

      // 🆕 支持两种命名方式：snake_case (Python) 和 camelCase (TypeScript)
      const effectiveSamplingConfig = sampling_config || samplingConfig;

      logWithTimestamp(`[API /api/sim/config] Received sampling_config: ${JSON.stringify(effectiveSamplingConfig)}`);

      const config = {
        agent_count: agentCount || 1000,
        platform: platform || "Reddit",
        recsys: recsys || "Hot-score",
        topics: topics || (topic ? [topic] : []),
        regions: regions || (region ? [region] : []),
        seed_posts: seedPosts || undefined,  // 🆕 自定义种子帖子
        sampling_config: effectiveSamplingConfig || undefined,  // 🆕 Agent sampling config (Issue #52)
      };

      const result = await callOasisEngine("initialize", config);

      // 🆕 Get actual status after initialize (to get total_posts, etc.)
      const statusResult = await callOasisEngine("status", {});

      simulationState = {
        ...simulationState,
        activeAgents: statusResult.data?.activeAgents ?? (result.agent_count || agentCount),
        running: true,
        paused: false,
        currentStep: 0,
        totalPosts: statusResult.data?.totalPosts ?? 0,  // 🆕 Get actual post count
        agents: result.agents || [],
        platform: result.platform || platform,
        recsys: result.recsys || recsys,
        topics: result.topics || config.topics,
        regions: result.regions || config.regions,
      };

      io.emit("stats_update", simulationState);
      res.json({ status: "ok", message: "Simulation configured with real OASIS", data: result });
    } catch (error: any) {
      console.error("Error configuring OASIS:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  app.post("/api/sim/step", async (req, res) => {
    try {
      if (!simulationState.running) {
        return res.json({ status: "error", message: "Simulation not running" });
      }

      const result = await callOasisEngine("step", {});
      
      simulationState.currentStep = result.current_step ?? (simulationState.currentStep + 1);
      simulationState.totalPosts = result.total_posts ?? simulationState.totalPosts;
      simulationState.polarization = result.polarization ?? simulationState.polarization;
      simulationState.activeAgents = result.active_agents ?? simulationState.activeAgents;

      // 🆕 OASIS Paper Metrics (Phase 5: propagation, round_comparison, herd_effect)
      simulationState.currentRound = result.current_round ?? simulationState.currentRound;
      simulationState.propagation = result.propagation ?? simulationState.propagation;
      simulationState.roundComparison = result.round_comparison ?? simulationState.roundComparison;
      simulationState.herdEffect = result.herd_effect ?? simulationState.herdEffect;

      // ⚠️ Deprecated: velocity, herdHhi (kept for backward compatibility)
      simulationState.velocity = result.velocity ?? simulationState.velocity;
      simulationState.herdHhi = result.herd_hhi ?? simulationState.herdHhi;

      // 🆕 Track initialization phase (Phase 4)
      simulationState.initializationPhase = result.initialization_phase || false;
      simulationState.initializationComplete = result.initialization_complete || false;

      // 处理多条日志（兼容单个 new_log 和 new_logs 数组）
      if (result.new_logs && Array.isArray(result.new_logs)) {
        result.new_logs.forEach((log: any) => {
          io.emit("new_log", {
            timestamp: log.timestamp || new Date().toISOString(),
            agentId: log.agent_id,
            actionType: log.action_type,
            content: log.content,
            reason: log.reason,
          });
        });
      } else if (result.new_log) {
        // 兼容旧格式（单个日志）
        io.emit("new_log", {
          timestamp: result.new_log.timestamp || new Date().toISOString(),
          agentId: result.new_log.agent_id,
          actionType: result.new_log.action_type,
          content: result.new_log.content,
          reason: result.new_log.reason,
        });
      }

      if (result.group_message) {
        io.emit("group_message", {
          id: Date.now().toString(),
          timestamp: new Date().toLocaleTimeString(),
          agentId: result.group_message.agent_id,
          agentName: result.group_message.agent_name,
          content: result.group_message.content,
        });
      }

      io.emit("stats_update", simulationState);
      // 附加 Python 引擎原始返回字段（sidecar_stats 等可观测字段）
      res.json({
        ...simulationState,
        sidecar_stats: result.sidecar_stats ?? null,
        step_time: result.step_time ?? null,
      });
    } catch (error: any) {
      console.error("Error executing OASIS step:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  app.get("/api/sim/status", (req, res) => {
    res.json({
      ...simulationState,
      oasis_ready: oasisReady,
    });
  });

  app.post("/api/sim/pause", async (req, res) => {
    try {
      simulationState.running = false;
      simulationState.paused = true;
      io.emit("stats_update", simulationState);
      console.log("⏸️  模拟已暂停");
      res.json({ status: "paused", ...simulationState });
    } catch (error: any) {
      console.error("Error pausing simulation:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  app.post("/api/sim/resume", async (req, res) => {
    try {
      simulationState.running = true;
      simulationState.paused = false;
      io.emit("stats_update", simulationState);
      console.log("▶️  模拟已恢复");
      res.json({ status: "resumed", ...simulationState });
    } catch (error: any) {
      console.error("Error resuming simulation:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  app.post("/api/sim/reset", async (req, res) => {
    try {
      await callOasisEngine("reset", {});

      simulationState = {
        running: false,
        paused: false,
        currentStep: 0,
        currentRound: null,
        activeAgents: 0,
        totalPosts: 0,
        polarization: 0.0,
        propagation: null,
        roundComparison: null,
        herdEffect: null,
        velocity: 0.0,
        herdHhi: 0.0,
        agents: [],
        platform: "Reddit",
        recsys: "Hot-score",
        topics: [],
        regions: [],
        initializationPhase: false,
        initializationComplete: false,
        oasis_ready: false,
      };

      io.emit("stats_update", simulationState);
      res.json({ status: "reset" });
    } catch (error: any) {
      console.error("Error resetting OASIS:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // ===== Intervention APIs =====

  // POST /api/sim/intervention/batch - Batch add controlled agents
  app.post("/api/sim/intervention/batch", async (req, res) => {
    try {
      const { intervention_types, initial_step } = req.body;

      if (!intervention_types || !Array.isArray(intervention_types) || intervention_types.length === 0) {
        return res.status(400).json({
          status: "error",
          message: "intervention_types must be a non-empty array"
        });
      }

      console.log(`[Intervention] Adding controlled agents: ${intervention_types.join(", ")}`);

      const result = await callOasisEngine("add_controlled_agents_batch", {
        intervention_types,
        initial_step: initial_step !== false  // default true
      });

      console.log(`[Intervention] Result:`, result);
      res.json(result);
    } catch (error: any) {
      console.error("[Intervention] Error:", error);
      res.status(500).json({
        status: "error",
        message: error.message || "Failed to add controlled agents"
      });
    }
  });

  // POST /api/sim/intervention/single - Add single controlled agent
  app.post("/api/sim/intervention/single", async (req, res) => {
    try {
      const { user_name, content, bio } = req.body;

      if (!user_name || !content) {
        return res.status(400).json({
          status: "error",
          message: "user_name and content are required"
        });
      }

      console.log(`[Intervention] Adding single controlled agent: ${user_name}`);

      const result = await callOasisEngine("add_controlled_agent", {
        user_name,
        content,
        bio: bio || "Controlled agent for intervention"
      });

      console.log(`[Intervention] Result:`, result);
      res.json(result);
    } catch (error: any) {
      console.error("[Intervention] Error:", error);
      res.status(500).json({
        status: "error",
        message: error.message || "Failed to add controlled agent"
      });
    }
  });

  // POST /api/sim/intervention/force-post - Force agent to post
  app.post("/api/sim/intervention/force-post", async (req, res) => {
    try {
      const { agent_id, content, refresh_recsys } = req.body;

      if (agent_id === undefined || !content) {
        return res.status(400).json({
          status: "error",
          message: "agent_id and content are required"
        });
      }

      const result = await callOasisEngine("force_agent_post", {
        agent_id,
        content,
        refresh_recsys: refresh_recsys !== false  // default true
      });

      res.json(result);
    } catch (error: any) {
      console.error("[Intervention] Error forcing post:", error);
      res.status(500).json({
        status: "error",
        message: error.message || "Failed to force post"
      });
    }
  });

  // POST /api/sim/intervention/force-comment - Force agent to comment
  app.post("/api/sim/intervention/force-comment", async (req, res) => {
    try {
      const { agent_id, post_id, content, refresh_recsys } = req.body;

      if (agent_id === undefined || post_id === undefined || !content) {
        return res.status(400).json({
          status: "error",
          message: "agent_id, post_id, and content are required"
        });
      }

      const result = await callOasisEngine("force_agent_comment", {
        agent_id,
        post_id,
        content,
        refresh_recsys: refresh_recsys !== false  // default true
      });

      res.json(result);
    } catch (error: any) {
      console.error("[Intervention] Error forcing comment:", error);
      res.status(500).json({
        status: "error",
        message: error.message || "Failed to force comment"
      });
    }
  });

  // GET /api/sim/intervention/list - List all controlled agents
  app.get("/api/sim/intervention/list", async (req, res) => {
    try {
      const result = await callOasisEngine("list_controlled_agents", {});
      res.json(result);
    } catch (error: any) {
      console.error("[Intervention] Error listing agents:", error);
      res.status(500).json({
        status: "error",
        message: error.message || "Failed to list controlled agents"
      });
    }
  });

  // ===== Seed Initial Content APIs =====

  // POST /api/sim/seed - Seed initial posts to activate environment
  app.post("/api/sim/seed", async (_req, res) => {
    try {
      logWithTimestamp(`[Seed] Seeding initial content to activate environment`);
      const result = await callOasisEngine("seed_initial_content", {});

      if (result.status === "ok") {
        logWithTimestamp(`[Seed] ✅ Seeded ${result.seeded_posts || 0} initial posts`);
      } else {
        logWithTimestamp(`[Seed] ⚠️ Seed failed: ${result.message}`);
      }

      res.json(result);
    } catch (error: any) {
      console.error("[Seed] Error seeding initial content:", error);
      res.status(500).json({
        status: "error",
        message: error.message || "Failed to seed initial content"
      });
    }
  });

  // ===== End Seed APIs =====

  // ===== R4-01: Propagation Visualization APIs =====

  // GET /api/analytics/propagation-summary
  app.get("/api/analytics/propagation-summary", async (req, res) => {
    try {
      const dbPath = process.env.OASIS_DB_PATH || path.join(__dirname, "oasis_simulation.db");
      if (!existsSync(dbPath)) {
        return res.json({ nodes: [], edges: [], metrics: { velocity: 0, coverage: 0, herdIndex: 0, totalNodes: 0, totalEdges: 0, activeAgents: 0, totalPosts: 0 } });
      }
      const db = new Database(dbPath, { readonly: true });
      const users: any[] = db.prepare(`SELECT user_id, user_name FROM user`).all();
      const posts: any[] = db.prepare(`SELECT post_id, user_id, content, created_at FROM post ORDER BY created_at`).all();
      const nodes: any[] = [];
      const edges: any[] = [];
      for (const u of users) {
        nodes.push({ id: `agent_${u.user_id}`, type: "agent", label: u.user_name || `Agent ${u.user_id}` });
      }
      for (const p of posts) {
        const nodeId = `post_${p.post_id}`;
        nodes.push({ id: nodeId, type: "content", label: (p.content || "").slice(0, 40) + ((p.content || "").length > 40 ? "..." : ""), step: p.created_at });
        edges.push({ source: `agent_${p.user_id}`, target: nodeId, type: "create", step: p.created_at });
      }
      const likes: any[] = db.prepare(`SELECT user_id, post_id, created_at FROM \`like\` ORDER BY created_at`).all();
      for (const l of likes) { edges.push({ source: `agent_${l.user_id}`, target: `post_${l.post_id}`, type: "like", step: l.created_at }); }
      const follows: any[] = db.prepare(`SELECT follower_id, followee_id, created_at FROM follow ORDER BY created_at`).all();
      for (const f of follows) { edges.push({ source: `agent_${f.follower_id}`, target: `agent_${f.followee_id}`, type: "follow", step: f.created_at }); }
      const comments: any[] = db.prepare(`SELECT user_id, post_id, created_at FROM comment ORDER BY created_at`).all();
      for (const c of comments) { edges.push({ source: `agent_${c.user_id}`, target: `post_${c.post_id}`, type: "reply", step: c.created_at }); }
      const activeAgentIds = new Set([...posts.map((p: any) => p.user_id), ...likes.map((l: any) => l.user_id), ...follows.map((f: any) => f.follower_id), ...comments.map((c: any) => c.user_id)]);
      const coverage = users.length > 0 ? activeAgentIds.size / users.length : 0;
      const totalInteractions = likes.length + follows.length + comments.length;
      const velocity = posts.length > 0 ? posts.length / Math.max(1, totalInteractions + posts.length) : 0;
      const traceRows: any[] = db.prepare(`SELECT action, COUNT(*) as cnt FROM trace GROUP BY action`).all();
      let totalActions = 0, herdIndex = 0;
      for (const row of traceRows) totalActions += row.cnt;
      for (const row of traceRows) { const s = row.cnt / Math.max(1, totalActions); herdIndex += s * s; }
      db.close();
      res.json({ nodes, edges, metrics: { velocity: parseFloat(velocity.toFixed(4)), coverage: parseFloat(coverage.toFixed(4)), herdIndex: parseFloat(herdIndex.toFixed(4)), totalNodes: nodes.length, totalEdges: edges.length, activeAgents: activeAgentIds.size, totalPosts: posts.length } });
    } catch (error: any) {
      console.error("Error fetching propagation summary:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // GET /api/analytics/opinion-distribution
  app.get("/api/analytics/opinion-distribution", async (req, res) => {
    try {
      const dbPath = process.env.OASIS_DB_PATH || path.join(__dirname, "oasis_simulation.db");
      if (!existsSync(dbPath)) {
        return res.json({ distribution: [{ name: "Left", value: 0, count: 0 }, { name: "Center", value: 0, count: 0 }, { name: "Right", value: 0, count: 0 }], total: 0 });
      }
      const db = new Database(dbPath, { readonly: true });
      const rows: any[] = db.prepare(`SELECT stance_score FROM polarization_cache WHERE stance_score IS NOT NULL`).all();
      db.close();
      let left = 0, center = 0, right = 0;
      for (const row of rows) { const s = row.stance_score; if (s < -0.2) left++; else if (s > 0.2) right++; else center++; }
      const total = Math.max(1, rows.length);
      res.json({ distribution: [{ name: "Left", value: parseFloat((left / total * 100).toFixed(1)), count: left }, { name: "Center", value: parseFloat((center / total * 100).toFixed(1)), count: center }, { name: "Right", value: parseFloat((right / total * 100).toFixed(1)), count: right }], total: rows.length });
    } catch (error: any) {
      console.error("Error fetching opinion distribution:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // GET /api/analytics/herd-index
  app.get("/api/analytics/herd-index", async (req, res) => {
    try {
      const dbPath = process.env.OASIS_DB_PATH || path.join(__dirname, "oasis_simulation.db");
      if (!existsSync(dbPath)) { return res.json({ trend: [], current: 0 }); }
      const db = new Database(dbPath, { readonly: true });
      const traceRows: any[] = db.prepare(`SELECT created_at as step, action FROM trace WHERE action NOT IN ('sign_up', 'refresh') ORDER BY created_at`).all();
      db.close();
      const stepMap: Record<string, Record<string, number>> = {};
      for (const row of traceRows) { const step = String(Math.floor(Number(row.step) || 0)); if (!stepMap[step]) stepMap[step] = {}; stepMap[step][row.action] = (stepMap[step][row.action] || 0) + 1; }
      const trend = Object.entries(stepMap).map(([step, actions]) => { const total = Object.values(actions).reduce((a: number, b: number) => a + b, 0); let hhi = 0; if (total > 0) for (const cnt of Object.values(actions)) { const s = cnt / total; hhi += s * s; } return { step: parseInt(step), herdIndex: parseFloat(hhi.toFixed(4)) }; }).sort((a, b) => a.step - b.step);
      const current = trend.length > 0 ? trend[trend.length - 1].herdIndex : 0;
      res.json({ trend, current });
    } catch (error: any) {
      console.error("Error fetching herd index:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // ===== End R4-01 APIs =====

  // ===== R4-02: Custom Dataset Import APIs =====

  // Configure multer for in-memory file upload (max 10MB)
  const upload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: 10 * 1024 * 1024 },
    fileFilter: (_req, file, cb) => {
      const allowed = ["application/json", "text/csv", "text/plain", "application/octet-stream"];
      const ext = path.extname(file.originalname).toLowerCase();
      if (allowed.includes(file.mimetype) || ext === ".json" || ext === ".csv") {
        cb(null, true);
      } else {
        cb(new Error(`Unsupported file type: ${file.mimetype} (${ext})`));
      }
    },
  });

  // Dataset schema validator
  function validateDataset(data: any): { valid: boolean; errors: string[]; warnings: string[]; stats: any } {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!data || typeof data !== "object") {
      errors.push("Root must be a JSON object");
      return { valid: false, errors, warnings, stats: {} };
    }

    // Users validation
    const users = data.users;
    if (!users) { errors.push("Missing required field: users"); }
    else if (!Array.isArray(users)) { errors.push("users must be an array"); }
    else {
      if (users.length === 0) warnings.push("users array is empty");
      const usernames = new Set<string>();
      const dupes: string[] = [];
      users.forEach((u: any, i: number) => {
        if (!u.username) errors.push(`users[${i}]: missing required field 'username'`);
        else {
          if (usernames.has(u.username)) dupes.push(u.username);
          usernames.add(u.username);
        }
      });
      if (dupes.length > 0) warnings.push(`Duplicate usernames detected: ${dupes.slice(0, 3).join(", ")}${dupes.length > 3 ? " ..." : ""}`);
    }

    // Relationships validation
    const rels = data.relationships;
    if (rels !== undefined) {
      if (!Array.isArray(rels)) errors.push("relationships must be an array");
      else {
        const usernames = new Set((users || []).map((u: any) => u.username));
        rels.forEach((r: any, i: number) => {
          if (!r.source) errors.push(`relationships[${i}]: missing 'source'`);
          if (!r.target) errors.push(`relationships[${i}]: missing 'target'`);
          if (r.source && !usernames.has(r.source)) warnings.push(`relationships[${i}]: source '${r.source}' not in users`);
          if (r.target && !usernames.has(r.target)) warnings.push(`relationships[${i}]: target '${r.target}' not in users`);
        });
      }
    }

    // Posts validation
    const posts = data.posts;
    if (posts !== undefined) {
      if (!Array.isArray(posts)) errors.push("posts must be an array");
      else {
        const usernames = new Set((users || []).map((u: any) => u.username));
        posts.forEach((p: any, i: number) => {
          if (!p.username) errors.push(`posts[${i}]: missing 'username'`);
          if (!p.content) errors.push(`posts[${i}]: missing 'content'`);
          if (p.username && !usernames.has(p.username)) warnings.push(`posts[${i}]: username '${p.username}' not in users`);
        });
      }
    }

    const stats = {
      users: Array.isArray(users) ? users.length : 0,
      relationships: Array.isArray(rels) ? rels.length : 0,
      posts: Array.isArray(posts) ? posts.length : 0,
    };

    return { valid: errors.length === 0, errors, warnings, stats };
  }

  // Convert CSV to DatasetBundle (minimal: users only)
  function csvToDataset(csvText: string): any {
    const lines = csvText.trim().split("\n");
    if (lines.length < 2) return { users: [] };
    const headers = lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
    const users = lines.slice(1).map((line) => {
      const vals = line.split(",").map((v) => v.trim().replace(/^"|"$/g, ""));
      const obj: any = {};
      headers.forEach((h, i) => { obj[h] = vals[i] || ""; });
      return obj;
    }).filter((u) => u.username || u.user_name || u.name);
    // Normalize field names
    return {
      users: users.map((u) => ({
        username: u.username || u.user_name || u.name || `user_${Math.random().toString(36).slice(2, 7)}`,
        realname: u.realname || u.real_name || u.display_name || "",
        bio: u.bio || u.description || "",
        persona: u.persona || u.personality || "",
        age: u.age ? parseInt(u.age) : undefined,
        gender: u.gender || "",
        mbti: u.mbti || "",
        country: u.country || u.region || "",
      })),
    };
  }

  // Convert DatasetBundle to OASIS agent config
  function toOasisAgentConfig(dataset: any): any[] {
    const users = dataset.users || [];
    return users.map((u: any, i: number) => ({
      agent_id: i,
      user_name: u.username,
      name: u.realname || u.username,
      bio: u.bio || `${u.username} is a social media user.`,
      persona: u.persona || "",
      age: u.age || null,
      gender: u.gender || null,
      mbti: u.mbti || null,
      country: u.country || null,
      interests: u.interests || [],
    }));
  }

  // POST /api/dataset/validate
  app.post("/api/dataset/validate", upload.single("file"), async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ status: "error", message: "No file uploaded" });
      }
      const ext = path.extname(req.file.originalname).toLowerCase();
      const content = req.file.buffer.toString("utf-8");
      let dataset: any;
      if (ext === ".csv") {
        dataset = csvToDataset(content);
      } else {
        try { dataset = JSON.parse(content); }
        catch (e) { return res.status(400).json({ status: "error", message: "Invalid JSON: " + (e as Error).message }); }
      }
      const result = validateDataset(dataset);
      const preview = {
        users: (dataset.users || []).slice(0, 5),
        relationships: (dataset.relationships || []).slice(0, 5),
        posts: (dataset.posts || []).slice(0, 5),
      };
      res.json({ status: result.valid ? "valid" : "invalid", ...result, preview, format: ext === ".csv" ? "csv" : "json" });
    } catch (error: any) {
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // POST /api/dataset/import
  app.post("/api/dataset/import", upload.single("file"), async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ status: "error", message: "No file uploaded" });
      }
      const ext = path.extname(req.file.originalname).toLowerCase();
      const content = req.file.buffer.toString("utf-8");
      let dataset: any;
      if (ext === ".csv") {
        dataset = csvToDataset(content);
      } else {
        try { dataset = JSON.parse(content); }
        catch (e) { return res.status(400).json({ status: "error", message: "Invalid JSON" }); }
      }
      const validation = validateDataset(dataset);
      if (!validation.valid) {
        return res.status(400).json({ status: "error", message: "Validation failed", errors: validation.errors });
      }
      const agentConfig = toOasisAgentConfig(dataset);
      // Return converted config + analytics stub
      const analytics = {
        opinionDistribution: { left: 0, center: validation.stats.users, right: 0 },
        totalAgents: validation.stats.users,
        totalPosts: validation.stats.posts,
        totalRelationships: validation.stats.relationships,
      };
      res.json({
        status: "success",
        message: `Imported ${validation.stats.users} users, ${validation.stats.posts} posts, ${validation.stats.relationships} relationships`,
        stats: validation.stats,
        warnings: validation.warnings,
        agentConfig: agentConfig.slice(0, 10), // Return first 10 as sample
        analytics,
      });
    } catch (error: any) {
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // ===== End R4-02 APIs =====

  // ===== Persona MongoDB APIs =====

  // POST /api/persona/mongodb/import - Import data to MongoDB
  app.post("/api/persona/mongodb/import", upload.single("file"), async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).json({ status: "error", message: "No file uploaded" });
      }

      const recsys_type = req.body.recsys_type;
      const type = req.body.type as "users" | "posts" | "replies" | "relationships" | "networks" | "topics";

      if (!recsys_type || !type) {
        return res.status(400).json({ status: "error", message: "Missing required fields: recsys_type, type" });
      }

      const validTypes = ["users", "posts", "replies", "relationships", "networks", "topics"];
      if (!validTypes.includes(type)) {
        return res.status(400).json({ status: "error", message: `Invalid type. Must be one of: ${validTypes.join(", ")}` });
      }

      const content = req.file.buffer.toString("utf-8");
      let data: any;

      try {
        data = JSON.parse(content);
      } catch (e) {
        return res.status(400).json({ status: "error", message: "Invalid JSON file" });
      }

      const collection = getCollection(getCollectionName(type));
      let imported = 0;

      if (type === "topics") {
        // topics: split by category
        const topicsData = [];
        for (const [category, topics] of Object.entries(data)) {
          topicsData.push({
            recsys_type,
            category,
            topics,
          });
        }
        await collection.insertMany(topicsData);
        imported = topicsData.length;
      } else if (type === "users") {
        // users: direct insert (has recsys_type field already)
        if (Array.isArray(data)) {
          await collection.insertMany(data);
          imported = data.length;
        } else {
          await collection.insertOne(data);
          imported = 1;
        }
      } else {
        // posts, replies, relationships, networks: add recsys_type
        if (Array.isArray(data)) {
          const dataWithPlatform = data.map((doc) => ({
            ...doc,
            recsys_type,
          }));
          await collection.insertMany(dataWithPlatform);
          imported = data.length;
        } else {
          await collection.insertOne({ ...data, recsys_type });
          imported = 1;
        }
      }

      res.json({
        status: "success",
        recsys_type,
        type,
        imported,
      });
    } catch (error: any) {
      console.error("[Persona Import Error]:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // POST /api/persona/twitter/fetch — 调用 fetch_twitter_data.py，返回用户/帖子等 JSON（不写库）
  app.post("/api/persona/twitter/fetch", (req, res) => {
    const pythonBin = path.join(__dirname, ".venv", "bin", "python");
    const scriptPath = path.join(__dirname, "oasis_dashboard", "datasets", "fetch_twitter_data.py");
    if (!existsSync(pythonBin)) {
      return res.status(500).json({
        status: "error",
        message: "未找到 .venv/bin/python，请先执行: uv sync",
      });
    }
    if (!existsSync(scriptPath)) {
      return res
        .status(404)
        .json({ status: "error", message: "未找到 oasis_dashboard/datasets/fetch_twitter_data.py" });
    }

    const b = (req.body && typeof req.body === "object" ? req.body : {}) as Record<string, unknown>;
    const opts: Record<string, number | string> = {};
    if (b.maxTrends != null) opts.maxTrends = Number(b.maxTrends);
    if (b.max_trends != null) opts.max_trends = Number(b.max_trends);
    if (b.maxPosts != null) opts.maxPosts = Number(b.maxPosts);
    if (b.max_posts != null) opts.max_posts = Number(b.max_posts);
    if (b.maxRepliesPerPost != null) opts.maxRepliesPerPost = Number(b.maxRepliesPerPost);
    if (b.max_replies_per_post != null) opts.max_replies_per_post = Number(b.max_replies_per_post);
    if (b.sortOrder != null) opts.sortOrder = String(b.sortOrder);
    if (b.sort_order != null) opts.sort_order = String(b.sort_order);

    const optsJson = JSON.stringify(opts);
    const child = spawn(pythonBin, [scriptPath, "--json", optsJson], {
      cwd: __dirname,
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c: Buffer) => {
      stdout += c.toString();
    });
    child.stderr.on("data", (c: Buffer) => {
      stderr += c.toString();
    });

    const timeoutMs = 600_000;
    const killTimer = setTimeout(() => {
      child.kill("SIGTERM");
    }, timeoutMs);

    child.on("error", (err) => {
      clearTimeout(killTimer);
      res.status(500).json({ status: "error", message: err.message });
    });

    child.on("close", (code) => {
      clearTimeout(killTimer);
      const trimmed = stdout.trim();
      if (code !== 0) {
        try {
          const parsed = JSON.parse(trimmed) as { error?: string; status_code?: number; type?: string };
          if (parsed?.error) {
            const sc =
              typeof parsed.status_code === "number" && parsed.status_code >= 400 && parsed.status_code < 600
                ? parsed.status_code
                : 502;
            return res.status(sc).json({
              status: "error",
              message: parsed.error,
              type: parsed.type,
              stderr: stderr.slice(-4000),
            });
          }
        } catch {
          /* fall through */
        }
        return res.status(500).json({
          status: "error",
          message: `Python 进程退出码 ${code}`,
          stderr: stderr.slice(-4000),
          stdoutPreview: trimmed.slice(0, 500),
        });
      }
      try {
        const data = JSON.parse(trimmed) as { error?: string };
        if (data?.error) {
          return res.status(500).json({ status: "error", ...data, stderr: stderr.slice(-2000) });
        }
        return res.json({ status: "ok", data });
      } catch {
        return res.status(500).json({
          status: "error",
          message: "无法解析 Python 输出的 JSON",
          stdoutPreview: trimmed.slice(0, 800),
          stderr: stderr.slice(-2000),
        });
      }
    });
  });

  // POST /api/persona/twitter/fetch-and-import — 抓取并写入 MongoDB（users/posts/topics）
  app.post("/api/persona/twitter/fetch-and-import", async (req, res) => {
    const recsys_type = "twitter";
    const pythonBin = path.join(__dirname, ".venv", "bin", "python");
    const scriptPath = path.join(__dirname, "oasis_dashboard", "datasets", "fetch_twitter_data.py");
    if (!existsSync(pythonBin)) {
      return res.status(500).json({
        status: "error",
        message: "未找到 .venv/bin/python，请先执行: uv sync",
      });
    }
    if (!existsSync(scriptPath)) {
      return res
        .status(404)
        .json({ status: "error", message: "未找到 oasis_dashboard/datasets/fetch_twitter_data.py" });
    }

    // Ensure MongoDB connection is available for this request
    try {
      await connectMongoDB();
    } catch (e: any) {
      return res.status(500).json({
        status: "error",
        message: `MongoDB 未连接：${e?.message || String(e)}`,
      });
    }

    const b = (req.body && typeof req.body === "object" ? req.body : {}) as Record<string, unknown>;
    const opts: Record<string, number | string> = {};
    if (b.maxTrends != null) opts.maxTrends = Number(b.maxTrends);
    if (b.max_trends != null) opts.max_trends = Number(b.max_trends);
    if (b.maxPosts != null) opts.maxPosts = Number(b.maxPosts);
    if (b.max_posts != null) opts.max_posts = Number(b.max_posts);
    if (b.maxRepliesPerPost != null) opts.maxRepliesPerPost = Number(b.maxRepliesPerPost);
    if (b.max_replies_per_post != null) opts.max_replies_per_post = Number(b.max_replies_per_post);
    if (b.sortOrder != null) opts.sortOrder = String(b.sortOrder);
    if (b.sort_order != null) opts.sort_order = String(b.sort_order);

    const wipe = Boolean(b.wipe); // 可选：wipe=true 时先清理 twitter 的旧数据（防止重复导入）

    const optsJson = JSON.stringify(opts);
    const child = spawn(pythonBin, [scriptPath, "--json", optsJson], {
      cwd: __dirname,
      env: { ...process.env },
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c: Buffer) => {
      stdout += c.toString();
    });
    child.stderr.on("data", (c: Buffer) => {
      stderr += c.toString();
    });

    const timeoutMs = 600_000;
    const killTimer = setTimeout(() => {
      child.kill("SIGTERM");
    }, timeoutMs);

    const finishWithPythonError = (code: number | null) => {
      clearTimeout(killTimer);
      const trimmed = stdout.trim();
      try {
        const parsed = JSON.parse(trimmed) as { error?: string; status_code?: number; type?: string };
        if (parsed?.error) {
          const sc =
            typeof parsed.status_code === "number" && parsed.status_code >= 400 && parsed.status_code < 600
              ? parsed.status_code
              : 502;
          return res.status(sc).json({
            status: "error",
            message: parsed.error,
            type: parsed.type,
            stderr: stderr.slice(-4000),
          });
        }
      } catch {
        /* ignore */
      }
      return res.status(500).json({
        status: "error",
        message: `Python 进程退出码 ${code}`,
        stderr: stderr.slice(-4000),
        stdoutPreview: trimmed.slice(0, 800),
      });
    };

    child.on("error", (err) => {
      clearTimeout(killTimer);
      res.status(500).json({ status: "error", message: err.message });
    });

    child.on("close", async (code) => {
      if (code !== 0) return finishWithPythonError(code);
      clearTimeout(killTimer);

      const trimmed = stdout.trim();
      let payload: any;
      try {
        payload = JSON.parse(trimmed);
      } catch {
        return res.status(500).json({
          status: "error",
          message: "无法解析 Python 输出的 JSON",
          stdoutPreview: trimmed.slice(0, 800),
          stderr: stderr.slice(-2000),
        });
      }

      if (payload?.error) {
        return res.status(500).json({ status: "error", ...payload, stderr: stderr.slice(-2000) });
      }

      const users = Array.isArray(payload?.users) ? payload.users : [];
      const posts = Array.isArray(payload?.posts) ? payload.posts : [];
      const topicsObj = (payload?.topics_document && typeof payload.topics_document === "object")
        ? payload.topics_document
        : (Array.isArray(payload?.topics) ? { twitter_trends: payload.topics } : {});

      try {
        const usersCol = getCollection(COLLECTIONS.USERS);
        const postsCol = getCollection(COLLECTIONS.POSTS);
        const topicsCol = getCollection(COLLECTIONS.TOPICS);

        if (wipe) {
          await Promise.all([
            usersCol.deleteMany({ recsys_type }),
            postsCol.deleteMany({ recsys_type }),
            topicsCol.deleteMany({ recsys_type }),
          ]);
        }

        let importedUsers = 0;
        let importedPosts = 0;
        let importedTopics = 0;

        if (users.length > 0) {
          await usersCol.insertMany(users, { ordered: false });
          importedUsers = users.length;
        }

        if (posts.length > 0) {
          const postsWithPlatform = posts.map((p: any) => ({ ...p, recsys_type }));
          await postsCol.insertMany(postsWithPlatform, { ordered: false });
          importedPosts = posts.length;
        }

        const topicsDocs: Array<{ recsys_type: string; category: string; topics: any }> = [];
        for (const [category, topics] of Object.entries(topicsObj)) {
          topicsDocs.push({ recsys_type, category, topics });
        }
        if (topicsDocs.length > 0) {
          await topicsCol.insertMany(topicsDocs, { ordered: false });
          importedTopics = topicsDocs.length;
        }

        return res.json({
          status: "success",
          recsys_type,
          imported: {
            users: importedUsers,
            posts: importedPosts,
            topics: importedTopics,
          },
          wipe,
          note: "本接口仅写入 users/posts/topics。replies/relationships/networks 需要对应结构化数据再导入。",
        });
      } catch (e: any) {
        return res.status(500).json({
          status: "error",
          message: e?.message || String(e),
        });
      }
    });
  });

  // GET /api/persona/:recsys_type/stats - Get platform statistics
  app.get("/api/persona/:recsys_type/stats", async (req, res) => {
    try {
      const { recsys_type } = req.params;

      const usersCollection = getCollection(COLLECTIONS.USERS);
      const postsCollection = getCollection(COLLECTIONS.POSTS);
      const repliesCollection = getCollection(COLLECTIONS.REPLIES);
      const relationshipsCollection = getCollection(COLLECTIONS.RELATIONSHIPS);
      const networksCollection = getCollection(COLLECTIONS.NETWORKS);
      const topicsCollection = getCollection(COLLECTIONS.TOPICS);

      const [usersCount, postsCount, repliesCount, relationshipsCount, networksCount, topicsCount] = await Promise.all([
        usersCollection.countDocuments({ recsys_type }),
        postsCollection.countDocuments({ recsys_type }),
        repliesCollection.countDocuments({ recsys_type }),
        relationshipsCollection.countDocuments({ recsys_type }),
        networksCollection.countDocuments({ recsys_type }),
        topicsCollection.countDocuments({ recsys_type }),
      ]);

      res.json({
        recsys_type,
        stats: {
          users: usersCount,
          posts: postsCount,
          replies: repliesCount,
          relationships: relationshipsCount,
          networks: networksCount,
          topics: topicsCount,
        },
      });
    } catch (error: any) {
      console.error("[Persona Stats Error]:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // GET /api/persona/:recsys_type/:type - Get data for a specific type
  app.get("/api/persona/:recsys_type/:type", async (req, res) => {
    try {
      const { recsys_type, type } = req.params;

      const validTypes = ["users", "posts", "replies", "relationships", "networks", "topics"];
      if (!validTypes.includes(type)) {
        return res.status(400).json({ status: "error", message: `Invalid type. Must be one of: ${validTypes.join(", ")}` });
      }

      const collection = getCollection(getCollectionName(type as any));
      const [data, count] = await Promise.all([
        collection.find({ recsys_type }, { projection: { _id: 0 } }).toArray(),
        collection.countDocuments({ recsys_type }),
      ]);

      res.json({
        recsys_type,
        type,
        stats: {
          count,
        },
        data,
      });
    } catch (error: any) {
      console.error("[Persona Query Error]:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // ===== End Persona MongoDB APIs =====

  // ===== R4-03: Unified Recommender Interface APIs =====

  // POST /api/recommender/rank
  // Body: { platform, user_id, candidates, context, config }
  app.post("/api/recommender/rank", async (req, res) => {
    try {
      const { platform, user_id = 0, candidates = [], context = {}, config } = req.body;
      if (!platform) return res.status(400).json({ error: "Missing required field: platform" });
      const supported = ["tiktok", "xiaohongshu", "pinterest"];
      if (!supported.includes(platform.toLowerCase())) {
        return res.status(400).json({ error: `Unsupported platform '${platform}'. Supported: ${supported.join(", ")}` });
      }
      if (!Array.isArray(candidates) || candidates.length === 0) {
        return res.status(400).json({ error: "candidates must be a non-empty array" });
      }
      // Delegate to Python recommender via child process
      const { execFileSync } = await import("child_process");
      const script = `
import json, sys
sys.path.insert(0, '${__dirname}')
from oasis_dashboard.recommender import get_recommender
platform = sys.argv[1]
user_id = int(sys.argv[2])
candidates = json.loads(sys.argv[3])
context = json.loads(sys.argv[4])
config = json.loads(sys.argv[5]) if sys.argv[5] != 'null' else None
rec = get_recommender(platform, config)
results = rec.rank(user_id, candidates, context)
print(json.dumps({'platform': platform, 'ranked': results}))
`;
      const output = execFileSync(
        `${__dirname}/.venv/bin/python`,
        ["-c", script, platform, String(user_id), JSON.stringify(candidates), JSON.stringify(context), JSON.stringify(config || null)],
        { encoding: "utf-8", maxBuffer: 10 * 1024 * 1024 }
      );
      const result = JSON.parse(output.trim());
      res.json(result);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  // POST /api/recommender/ab-compare
  // Body: { user_id, candidates, context, platforms, top_k, configs }
  app.post("/api/recommender/ab-compare", async (req, res) => {
    try {
      const { user_id = 0, candidates = [], context = {}, platforms, top_k = 5, configs } = req.body;
      if (!Array.isArray(candidates) || candidates.length === 0) {
        return res.status(400).json({ error: "candidates must be a non-empty array" });
      }
      const { execFileSync } = await import("child_process");
      const script = `
import json, sys
sys.path.insert(0, '${__dirname}')
from oasis_dashboard.recommender import ab_compare
user_id = int(sys.argv[1])
candidates = json.loads(sys.argv[2])
context = json.loads(sys.argv[3])
platforms = json.loads(sys.argv[4]) if sys.argv[4] != 'null' else None
top_k = int(sys.argv[5])
configs = json.loads(sys.argv[6]) if sys.argv[6] != 'null' else None
result = ab_compare(user_id, candidates, context, platforms, top_k, configs)
print(json.dumps(result))
`;
      const output = execFileSync(
        `${__dirname}/.venv/bin/python`,
        ["-c", script, String(user_id), JSON.stringify(candidates), JSON.stringify(context),
          JSON.stringify(platforms || null), String(top_k), JSON.stringify(configs || null)],
        { encoding: "utf-8", maxBuffer: 10 * 1024 * 1024 }
      );
      const result = JSON.parse(output.trim());
      res.json(result);
    } catch (error: any) {
      res.status(500).json({ error: error.message });
    }
  });

  // GET /api/recommender/platforms
  app.get("/api/recommender/platforms", (_req, res) => {
    res.json({
      platforms: [
        { id: "tiktok", name: "TikTok", description: "短期兴趣 + 完播率 + 互动 + 新鲜度", weights: { short_term_weight: 0.35, completion_weight: 0.25, engagement_weight: 0.20, freshness_weight: 0.20 } },
        { id: "xiaohongshu", name: "小红书", description: "内容质量 + 社交亲密度 + 搜索意图 + 新鲜度", weights: { quality_weight: 0.35, social_weight: 0.30, search_weight: 0.20, freshness_weight: 0.15 } },
        { id: "pinterest", name: "Pinterest", description: "长期兴趣 + 画板相似度 + 视觉/主题相似度 + 新鲜度", weights: { long_term_weight: 0.40, board_weight: 0.30, topic_weight: 0.20, freshness_weight: 0.10 } },
      ]
    });
  });

  // ===== End R4-03 APIs =====

  // ===== R6 Experiment APIs =====

  // POST /api/experiments/run
  app.post("/api/experiments/run", async (req, res) => {
    try {
      const { name, datasetId, recommenders, platform, steps, seed, agentCount } = req.body;
      if (!recommenders || recommenders.length < 1) {
        return res.status(400).json({ error: "At least one recommender required" });
      }

      const datasetFile = datasetId && datasetId !== 'demo'
        ? path.join(__dirname, "artifacts", "r5", `${datasetId}.json`)
        : path.join(__dirname, "artifacts", "r5", "dataset_demo_reddit.json");
      const datasetPath = existsSync(datasetFile)
        ? datasetFile
        : path.join(__dirname, "artifacts", "r5", "dataset_demo_reddit.json");

      const experimentName = (name || `exp_${Date.now()}`).replace(/[^a-zA-Z0-9_-]/g, '_');
      const outputDir = path.join(__dirname, "artifacts", "experiments", experimentName);

      const { execSync } = await import('child_process');
      const helperScript = path.join(__dirname, 'oasis_dashboard', 'run_experiment_helper.py');
      const cmd = [
        'python3.11',
        helperScript,
        '--name', experimentName,
        '--dataset-id', datasetId || 'demo',
        '--dataset-path', datasetPath,
        '--recommenders', JSON.stringify(recommenders),
        '--platform', platform || 'REDDIT',
        '--steps', String(steps || 15),
        '--seed', String(seed || 42),
        '--agent-count', String(agentCount || 10),
        '--output-dir', outputDir,
      ];

      const output = execSync(cmd.map(c => `"${c.replace(/"/g, '\\"')}"`).join(' '), {
        cwd: __dirname,
        timeout: 120000,
        maxBuffer: 10 * 1024 * 1024,
        env: { ...process.env },
        shell: '/bin/bash',
      } as any);
      const result = JSON.parse(output.toString().trim());
      res.json({ success: true, ...result });
    } catch (err: any) {
      console.error('Experiment run error:', err.stderr?.toString() || err.message);
      res.status(500).json({ error: err.stderr?.toString() || err.message || 'Experiment failed' });
    }
  });

  // GET /api/experiments - list all experiments
  app.get("/api/experiments", async (_req, res) => {
    try {
      const experimentsDir = path.join(__dirname, "artifacts", "experiments");
      if (!existsSync(experimentsDir)) {
        return res.json({ experiments: [] });
      }
      const { readdirSync, statSync, readFileSync: rfs } = await import('fs');
      const dirs = readdirSync(experimentsDir).filter((d: string) => {
        try { return statSync(path.join(experimentsDir, d)).isDirectory(); } catch { return false; }
      });
      const experiments = dirs.map((dir: string) => {
        const configPath = path.join(experimentsDir, dir, 'config.json');
        const resultPath = path.join(experimentsDir, dir, 'result.json');
        try {
          const config = JSON.parse(rfs(configPath, 'utf-8') as string);
          let summary: any = {};
          if (existsSync(resultPath)) {
            const result = JSON.parse(rfs(resultPath, 'utf-8') as string);
            const runs = result.runs || [];
            if (runs.length > 0) {
              summary = {
                bestPolarization: Math.max(...runs.map((r: any) => r.metrics?.polarization_final || 0)),
                bestVelocity: Math.max(...runs.map((r: any) => r.metrics?.velocity_avg || 0)),
                totalPosts: runs.reduce((s: number, r: any) => s + (r.metrics?.total_posts || 0), 0),
              };
            }
          }
          const resultData = existsSync(resultPath) ? JSON.parse(rfs(resultPath, 'utf-8') as string) : {};
          return {
            experimentId: resultData.experimentId || dir,
            name: config.name || dir,
            datasetId: config.datasetId,
            recommenders: config.recommenders || [],
            steps: config.steps,
            seed: config.seed,
            createdAt: statSync(configPath).mtime.toISOString(),
            summary,
          };
        } catch {
          return { experimentId: dir, name: dir, datasetId: '', recommenders: [], steps: 0, seed: 0, createdAt: '', summary: {} };
        }
      });
      res.json({ experiments });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // GET /api/experiments/:id/result
  app.get("/api/experiments/:id/result", async (req, res) => {
    try {
      const { id } = req.params;
      const experimentsDir = path.join(__dirname, "artifacts", "experiments");
      const { readdirSync, readFileSync: rfs } = await import('fs');
      let resultPath: string | null = null;
      if (existsSync(experimentsDir)) {
        const dirs = readdirSync(experimentsDir);
        for (const dir of dirs) {
          const rp = path.join(experimentsDir, dir, 'result.json');
          if (existsSync(rp)) {
            const data = JSON.parse(rfs(rp, 'utf-8') as string);
            if (data.experimentId === id || dir === id) {
              resultPath = rp;
              break;
            }
          }
        }
      }
      if (!resultPath) {
        return res.status(404).json({ error: 'Experiment not found' });
      }
      const { readFileSync: rfs2 } = await import('fs');
      const result = JSON.parse(rfs2(resultPath, 'utf-8') as string);
      res.json(result);
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // ===== End R6 Experiment APIs =====

  app.get("/api/sim/logs", async (req, res) => {
    try {
      const dbPath = process.env.OASIS_DB_PATH || path.join(__dirname, "oasis_simulation.db");

      if (!existsSync(dbPath)) {
        return res.json({ logs: [] });
      }

      const db = new Database(dbPath, { readonly: true });

      const query = `
        SELECT
          user_id as agentId,
          created_at as timestamp,
          action as actionType,
          info as content
        FROM trace
        ORDER BY created_at DESC
        LIMIT 500
      `;

      const rows: any[] = db.prepare(query).all();
      db.close();

      const logs = rows.map(row => ({
        agentId: `agent_${row.agentId}`,
        timestamp: row.timestamp,
        actionType: row.actionType,
        content: row.content || "",
        reason: ""
      }));

      res.json({ logs });
    } catch (error: any) {
      console.error("Error fetching logs:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  app.post("/api/users/generate", async (req, res) => {
    try {
      const { platform, count, seed, topics, regions, topic, region } = req.body;
      const finalTopics = topics || (topic ? [topic] : []);
      const finalRegions = regions || (region ? [region] : []);
      
      const result = await callOasisEngine("generate_users", {
        platform: platform || "Reddit",
        count: count || 10,
        seed: seed,
        topics: finalTopics,
        regions: finalRegions,
      });

      res.json({
        status: "success",
        total_generated: result.total_generated || count,
        agents: result.agents || [],
      });
    } catch (error: any) {
      console.error("Error generating users:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  app.post("/api/sim/group-message", async (req, res) => {
    try {
      const { content, agentName } = req.body;
      
      const result = await callOasisEngine("inject_message", {
        content: content,
        agent_name: agentName || "人工注入",
      });

      const msg = {
        id: Date.now().toString(),
        timestamp: new Date().toLocaleTimeString(),
        agentId: "manual",
        agentName: agentName || "人工注入",
        content: content,
      };

      io.emit("group_message", msg);
      res.json(msg);
    } catch (error: any) {
      console.error("Error injecting message:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      configFile: path.join(__dirname, 'vite.config.ts'),
      server: { 
        middlewareMode: true,
      },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.join(__dirname, "dist")));
    app.get("*", (req, res) => {
      res.sendFile(path.join(__dirname, "dist", "index.html"));
    });
  }

  httpServer.listen(PORT, "0.0.0.0", () => {
    console.log(`✅ Server running on http://localhost:${PORT}`);
    console.log(`✅ Real OASIS Engine integration enabled`);
  });

  // Cleanup on exit
  process.on("SIGINT", () => {
    console.log("Shutting down...");
    if (restartTimeout) {
      clearTimeout(restartTimeout);
    }
    if (oasisProcess) {
      oasisProcess.kill();
    }
    process.exit(0);
  });
}

startServer();
