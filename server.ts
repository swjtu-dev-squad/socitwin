import express from "express";
import { createServer } from "http";
import { Server } from "socket.io";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";
import { watch } from "fs";
import { existsSync } from "fs";
import Database from "better-sqlite3";

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
      
      simulationState.currentStep = result.current_step || simulationState.currentStep + 1;
      simulationState.totalPosts = result.total_posts || simulationState.totalPosts;
      simulationState.polarization = result.polarization || simulationState.polarization;
      simulationState.activeAgents = result.active_agents || simulationState.activeAgents;

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
      res.json(simulationState);
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
      };

      io.emit("stats_update", simulationState);
      res.json({ status: "reset" });
    } catch (error: any) {
      console.error("Error resetting OASIS:", error);
      res.status(500).json({ status: "error", message: error.message });
    }
  });

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
