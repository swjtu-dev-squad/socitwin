import express from "express";
import { createServer } from "http";
import { Server } from "socket.io";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

  // Simulation State
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

  const getMockAgents = (count: number) => {
    return Array.from({ length: Math.min(count, 50) }, (_, i) => ({
      id: `a${i}`,
      name: `Agent_${i}`,
      bio: `I am an AI agent interested in ${['AI', 'Politics', 'Tech', 'Art'][i % 4]}`,
      interests: [['AI', 'Tech'], ['Politics', 'News'], ['Art', 'Design']][i % 3],
      status: i % 5 === 0 ? 'active' : 'idle',
      lastAction: i % 3 === 0 ? 'CREATE_POST' : undefined,
      polarization: Math.random()
    }));
  };

  // API Routes
  app.post("/api/sim/config", (req, res) => {
    const { agentCount, platform, recsys, topics, regions, topic, region } = req.body;
    simulationState = {
      ...simulationState,
      activeAgents: agentCount || 1000,
      running: true,
      currentStep: 0,
      agents: getMockAgents(agentCount || 1000),
      platform: platform || simulationState.platform,
      recsys: recsys || simulationState.recsys,
      topics: topics || (topic ? [topic] : []),
      regions: regions || (region ? [region] : []),
    };
    io.emit("stats_update", simulationState);
    res.json({ status: "ok", message: "Simulation configured" });
  });

  app.post("/api/sim/step", (req, res) => {
    if (simulationState.running) {
      simulationState.currentStep += 1;
      simulationState.totalPosts += Math.floor(Math.random() * 50);
      simulationState.polarization = Math.min(1, simulationState.polarization + Math.random() * 0.05);
      
      const newLog = {
        timestamp: new Date().toLocaleTimeString(),
        agentId: `a${Math.floor(Math.random() * 1000)}`,
        actionType: ["CREATE_POST", "LIKE_POST", "FOLLOW", "REPORT_POST"][Math.floor(Math.random() * 4)],
        content: "Random simulation content...",
        reason: "LLM decision based on context",
      };
      
      io.emit("stats_update", simulationState);
      io.emit("new_log", newLog);
      
      if (Math.random() > 0.7) {
        io.emit("group_message", {
          id: Date.now().toString(),
          timestamp: new Date().toLocaleTimeString(),
          agentId: `a${Math.floor(Math.random() * 1000)}`,
          agentName: "Agent_" + Math.floor(Math.random() * 100),
          content: "Group discussion message...",
        });
      }
    }
    res.json(simulationState);
  });

  app.get("/api/sim/status", (req, res) => {
    res.json(simulationState);
  });

  app.post("/api/sim/reset", (req, res) => {
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
  });

  app.post("/api/users/generate", (req, res) => {
    const { platform, count, seed, topics, regions, topic, region } = req.body;
    const finalTopics = topics || (topic ? [topic] : []);
    const finalRegions = regions || (region ? [region] : []);
    
    const agents = Array.from({ length: Math.min(count || 10, 100) }, (_, i) => ({
      id: `a${i}_${seed}`,
      name: `Agent_${i}`,
      bio: `Simulated bio for ${platform} user in ${finalRegions[0] || 'Global'}. Interested in ${finalTopics[0] || platform} dynamics.`,
      interests: [...finalTopics, platform, "Social", ...finalRegions],
    }));

    res.json({
      status: "success",
      total_generated: count,
      agents: agents,
    });
  });

  app.post("/api/sim/group-message", (req, res) => {
    const { content, agentName } = req.body;
    const msg = {
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString(),
      agentId: "manual",
      agentName: agentName || "人工注入",
      content: content,
    };
    io.emit("group_message", msg);
    res.json(msg);
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
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
