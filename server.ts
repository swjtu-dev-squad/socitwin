import express from "express";
import { createServer } from "http";
import multer from "multer";
import { readFileSync } from "fs";
import { Server } from "socket.io";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";
import { watch } from "fs";
import { existsSync } from "fs";
import Database from "better-sqlite3";
import dotenv from "dotenv";

// Load environment variables from .env file
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Python OASIS Engine Process
let oasisProcess: any = null;
let oasisReady = false;
let restartTimeout: NodeJS.Timeout | null = null;
let ioInstance: any = null;

function startOasisEngine() {
  console.log("Starting OASIS Engine...");
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
    },
  });

  oasisProcess.stdout.on("data", (data: Buffer) => {
    const output = data.toString();
    console.log(`[OASIS Engine] ${output}`);
    // Check for ready signal from JSON-RPC server
    if (output.includes('"status":"ready"') || output.includes("ready")) {
      oasisReady = true;
      console.log("✅ OASIS Engine ready!");
    }
  });

  oasisProcess.stderr.on("data", (data: Buffer) => {
    const output = data.toString();

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

  // Start OASIS Engine (uses ioInstance for progress updates)
  startOasisEngine();

  // Watch Python files for hot reload
  watchPythonFiles();

  // Simulation State (cached from OASIS)
  let simulationState = {
    running: false,
    paused: false,
    currentStep: 0,
    activeAgents: 0,
    totalPosts: 0,
    polarization: 0.0,
    velocity: 0.0,           // 🆕 Information velocity (posts/second)
    herdHhi: 0.0,            // 🆕 Herd effect index (normalized HHI)
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
      const { agentCount, platform, recsys, topics, regions, topic, region } = req.body;
      
      const config = {
        agent_count: agentCount || 1000,
        platform: platform || "Reddit",
        recsys: recsys || "Hot-score",
        topics: topics || (topic ? [topic] : []),
        regions: regions || (region ? [region] : []),
      };

      const result = await callOasisEngine("initialize", config);
      
      simulationState = {
        ...simulationState,
        activeAgents: result.agent_count || agentCount,
        running: true,
        paused: false,
        currentStep: 0,
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

      // 🆕 Update new metrics (Phase 5: velocity + herd effect)
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
        activeAgents: 0,
        totalPosts: 0,
        polarization: 0.0,
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
