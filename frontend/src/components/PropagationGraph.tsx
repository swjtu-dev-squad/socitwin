import { useEffect, useRef, useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";

interface PropNode {
  id: string;
  type: "agent" | "content";
  label: string;
  step?: number | string;
}

interface PropEdge {
  source: string;
  target: string;
  type: "create" | "like" | "follow" | "reply";
  step?: number | string;
}

interface PropagationMetrics {
  velocity: number;
  coverage: number;
  herdIndex: number;
  totalNodes: number;
  totalEdges: number;
  activeAgents: number;
  totalPosts: number;
}

interface PropagationData {
  nodes: PropNode[];
  edges: PropEdge[];
  metrics: PropagationMetrics;
}

const EDGE_COLORS: Record<string, string> = {
  create: "#6366f1",
  like: "#f59e0b",
  follow: "#10b981",
  reply: "#3b82f6",
};

const NODE_COLORS: Record<string, string> = {
  agent: "#818cf8",
  content: "#34d399",
};

export function PropagationGraph() {
  const [data, setData] = useState<PropagationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<PropNode | null>(null);
  const [filterType, setFilterType] = useState<string>("all");
  const graphRef = useRef<any>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/analytics/propagation-summary");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const graphData = useCallback(() => {
    if (!data) return { nodes: [], links: [] };
    const filteredEdges =
      filterType === "all"
        ? data.edges
        : data.edges.filter((e) => e.type === filterType);

    const usedNodeIds = new Set<string>();
    for (const e of filteredEdges) {
      usedNodeIds.add(typeof e.source === "object" ? (e.source as any).id : e.source);
      usedNodeIds.add(typeof e.target === "object" ? (e.target as any).id : e.target);
    }
    const nodes =
      filterType === "all"
        ? data.nodes
        : data.nodes.filter((n) => usedNodeIds.has(n.id));

    return {
      nodes: nodes.map((n) => ({ ...n })),
      links: filteredEdges.map((e) => ({
        source: typeof e.source === "object" ? (e.source as any).id : e.source,
        target: typeof e.target === "object" ? (e.target as any).id : e.target,
        type: e.type,
        color: EDGE_COLORS[e.type] || "#888",
      })),
    };
  }, [data, filterType]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-48 text-text-tertiary">
        <div className="text-center">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-2" />
          <p className="text-xs">加载传播图数据...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-48 text-red-400">
        <p className="text-xs">加载失败: {error}</p>
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-text-tertiary">
        <div className="text-center">
          <p className="text-sm font-medium">暂无传播数据</p>
          <p className="text-xs mt-1 opacity-70">运行模拟后将显示传播图</p>
        </div>
      </div>
    );
  }

  const gd = graphData();

  return (
    <div className="flex flex-col gap-3">
      {/* Metrics Row */}
      <div className="grid grid-cols-4 gap-2 text-xs">
        <div className="bg-bg-primary rounded p-2 text-center">
          <div className="text-accent font-bold text-base">{data.metrics.totalNodes}</div>
          <div className="text-text-tertiary">节点</div>
        </div>
        <div className="bg-bg-primary rounded p-2 text-center">
          <div className="text-accent font-bold text-base">{data.metrics.totalEdges}</div>
          <div className="text-text-tertiary">边</div>
        </div>
        <div className="bg-bg-primary rounded p-2 text-center">
          <div className="text-accent font-bold text-base">{(data.metrics.coverage * 100).toFixed(0)}%</div>
          <div className="text-text-tertiary">覆盖率</div>
        </div>
        <div className="bg-bg-primary rounded p-2 text-center">
          <div className="text-accent font-bold text-base">{(data.metrics.herdIndex * 100).toFixed(0)}%</div>
          <div className="text-text-tertiary">羊群指数</div>
        </div>
      </div>

      {/* Filter Row */}
      <div className="flex gap-2 flex-wrap">
        {["all", "create", "like", "follow", "reply"].map((t) => (
          <button
            key={t}
            onClick={() => setFilterType(t)}
            className={`px-2 py-1 rounded text-xs font-medium transition-colors ${
              filterType === t
                ? "bg-accent text-white"
                : "bg-bg-primary text-text-secondary hover:bg-bg-tertiary"
            }`}
          >
            {t === "all" ? "全部" : t}
            {t !== "all" && (
              <span
                className="inline-block w-2 h-2 rounded-full ml-1"
                style={{ backgroundColor: EDGE_COLORS[t] }}
              />
            )}
          </button>
        ))}
        <button
          onClick={fetchData}
          className="ml-auto px-2 py-1 rounded text-xs bg-bg-primary text-text-secondary hover:bg-bg-tertiary"
        >
          刷新
        </button>
      </div>

      {/* Graph */}
      <div className="relative rounded overflow-hidden bg-bg-primary" style={{ height: 280 }}>
        <ForceGraph2D
          ref={graphRef}
          graphData={gd}
          width={undefined}
          height={280}
          backgroundColor="#0f172a"
          nodeLabel={(node: any) => node.label || node.id}
          nodeColor={(node: any) => NODE_COLORS[node.type] || "#888"}
          nodeRelSize={5}
          linkColor={(link: any) => link.color || "#555"}
          linkWidth={1.5}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          onNodeClick={(node: any) => setSelectedNode(node as PropNode)}
          cooldownTicks={80}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const label = (node.label || node.id).slice(0, 20);
            const fontSize = Math.max(8, 12 / globalScale);
            const r = node.type === "agent" ? 5 : 4;
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fillStyle = NODE_COLORS[node.type] || "#888";
            ctx.fill();
            if (globalScale >= 1.5) {
              ctx.font = `${fontSize}px Sans-Serif`;
              ctx.fillStyle = "#e2e8f0";
              ctx.textAlign = "center";
              ctx.fillText(label, node.x, node.y + r + fontSize);
            }
          }}
        />
        {/* Legend */}
        <div className="absolute bottom-2 left-2 flex flex-col gap-1 text-[10px] text-text-tertiary">
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: NODE_COLORS.agent }} />
            Agent
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: NODE_COLORS.content }} />
            Content
          </div>
        </div>
      </div>

      {/* Selected Node Detail */}
      {selectedNode && (
        <div className="bg-bg-primary rounded p-3 text-xs">
          <div className="flex justify-between items-start">
            <div>
              <span className="font-bold text-accent">{selectedNode.type === "agent" ? "Agent" : "Post"}</span>
              <span className="ml-2 text-text-secondary">{selectedNode.id}</span>
            </div>
            <button onClick={() => setSelectedNode(null)} className="text-text-tertiary hover:text-text-primary">✕</button>
          </div>
          <p className="mt-1 text-text-secondary">{selectedNode.label}</p>
        </div>
      )}
    </div>
  );
}
