import express from "express";
import { createServer } from "http";
import { Server } from "socket.io";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Python OASIS Engine Process
let oasisProcess: any = null;
let oasisReady = false;

function startOasisEngine() {
  console.log("Starting OASIS Engine...");
  oasisProcess = spawn("python3", [path.join(__dirname, "real_oasis_engine_v3.py"), "--rpc"], {
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
    console.error(`[OASIS Engine Error] ${data.toString()}`);
  });

  oasisProcess.on("close", (code: number) => {
    console.log(`OASIS Engine process exited with code ${code}`);
    oasisReady = false;
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
    }, 30000); // 30 seconds timeout
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

  const PORT = 3000;

  app.use(express.json());

  // Start OASIS Engine
  startOasisEngine();

  // Simulation State (cached from OASIS)
  let simulationState = {
    running: false,
    currentStep: 0,
    activeAgents: 0,
    totalPosts: 0,
    polarization: 0.0,
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
      
      if (result.new_log) {
        io.emit("new_log", {
          timestamp: new Date().toLocaleTimeString(),
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

  app.post("/api/sim/reset", async (req, res) => {
    try {
      await callOasisEngine("reset", {});
      
      simulationState = {
        running: false,
        currentStep: 0,
        activeAgents: 0,
        totalPosts: 0,
        polarization: 0.0,
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
    if (oasisProcess) {
      oasisProcess.kill();
    }
    process.exit(0);
  });
}

startServer();
