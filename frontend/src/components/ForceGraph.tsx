import ForceGraph2D from 'react-force-graph-2d';
import { useMemo, useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';
import type { AgentGraphEdge, AgentGraphNode } from '@/lib/agentMonitorTypes';

type ForceGraphProps = {
  agents?: any[];
  nodes?: AgentGraphNode[];
  edges?: AgentGraphEdge[];
  onNodeClick?: (agent: any) => void;
  focusId?: string | null;
};

export function ForceGraph({ agents, nodes, edges, onNodeClick, focusId }: ForceGraphProps) {
  const fgRef = useRef<any>(undefined);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });

  // 监听容器大小变化
  useEffect(() => {
    if (!containerRef.current) return;
    
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
          setDimensions({
            width: entry.contentRect.width,
            height: entry.contentRect.height
          });
        }
      }
    });

    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const sourceNodes = nodes && nodes.length > 0
      ? nodes
      : (agents || []).map((agent: any) => ({
          id: agent.id,
          name: agent.name || 'Unknown Agent',
          role: agent.role || 'Neutral',
          roleLabel: agent.roleLabel || agent.role || 'Neutral',
          influence: agent.influence || 0,
          activity: agent.activity || 0,
          status: agent.status || 'idle',
          country: agent.country,
          city: agent.city,
        }));

    const sourceEdges = edges && edges.length > 0
      ? edges
      : (agents || []).flatMap((agent: any) => {
          const followEdges = Array.isArray(agent.following)
            ? agent.following.map((targetId: string) => ({
                source: agent.id,
                target: targetId,
                type: 'follow' as const,
              }))
            : [];
          const interactionEdge = agent.lastAction?.targetAgentId
            ? [{
                source: agent.id,
                target: agent.lastAction.targetAgentId,
                type: 'interaction' as const,
                actionType: agent.lastAction.type,
                active: true,
              }]
            : [];
          return [...followEdges, ...interactionEdge];
        });

    return {
      nodes: sourceNodes.map((node) => ({
        ...node,
        val: Math.max(6, Math.round((node.influence || 0) / 4) || 6),
        color: getRoleColor(node.roleLabel || node.role),
        isKOL: /kol/i.test(node.roleLabel || node.role),
      })),
      links: sourceEdges.map((edge) => ({
        ...edge,
        color: edge.type === 'follow' ? 'rgba(59, 130, 246, 0.24)' : getActionColor(edge.actionType || 'interaction'),
        width: edge.active ? 2.5 : edge.type === 'interaction' ? 1.8 : 1,
      })),
    };
  }, [agents, nodes, edges]);

  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      // 增加力导向图的中心力，确保它在画布中央
      fgRef.current.d3Force('center', d3.forceCenter(dimensions.width / 2, dimensions.height / 2));
      
      // 增加排斥力，防止节点重叠
      fgRef.current.d3Force('charge').strength(-150);
      
      // 增加碰撞力
      fgRef.current.d3Force('collide', d3.forceCollide((node: any) => node.val + 5));

      // 自动缩放
      setTimeout(() => {
        fgRef.current.zoomToFit(400, 50);
        fgRef.current.d3ReheatSimulation();
      }, 100);
    }
  }, [graphData.nodes.length, dimensions.width, dimensions.height]);

  if (graphData.nodes.length > 0 && graphData.links.length === 0) {
    const safeWidth = Math.max(dimensions.width, 640);
    const safeHeight = Math.max(dimensions.height, 360);
    const centerX = safeWidth / 2;
    const centerY = safeHeight / 2;
    const radius = Math.min(safeWidth, safeHeight) * 0.28;

    return (
      <div
        ref={containerRef}
        className="w-full h-full min-h-0 relative overflow-hidden bg-[radial-gradient(circle_at_50%_35%,rgba(16,185,129,0.12),transparent_42%)]"
      >
        {graphData.nodes.map((node: any, index: number) => {
          const angle = (Math.PI * 2 * index) / Math.max(graphData.nodes.length, 1) - Math.PI / 2;
          const x = centerX + Math.cos(angle) * radius;
          const y = centerY + Math.sin(angle) * radius;
          const size = Math.max(18, node.val * 2.2);
          const selected = node.id === focusId;

          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onNodeClick?.(node.id)}
              className="absolute -translate-x-1/2 -translate-y-1/2 text-left"
              style={{ left: x, top: y }}
            >
              <div
                className="rounded-full border transition-all duration-200"
                style={{
                  width: size,
                  height: size,
                  background: node.color,
                  borderColor: selected ? '#ffffff' : 'rgba(255,255,255,0.14)',
                  boxShadow: selected
                    ? `0 0 0 4px ${node.color}33, 0 0 24px ${node.color}88`
                    : `0 0 18px ${node.color}55`,
                }}
              />
              <div className="mt-3 min-w-[96px] -translate-x-1/3 rounded-xl border border-white/8 bg-black/40 px-3 py-2 backdrop-blur-sm">
                <p className="text-xs font-semibold text-white">{node.name}</p>
                <p className="mt-1 text-[10px] uppercase tracking-wide text-white/55">{node.roleLabel || node.role}</p>
                <p className="mt-1 text-[10px] text-emerald-300">活跃度 {node.activity}%</p>
              </div>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full min-h-0 flex items-center justify-center">
      {dimensions.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          cooldownTicks={100}
          nodeRelSize={1}
          nodeLabel={(node: any) => `
            <div class="bg-bg-secondary p-2 rounded-lg border border-border-default shadow-xl text-text-primary">
              <p class="font-bold text-accent">${node.name}</p>
              <p class="text-[10px] text-text-tertiary uppercase font-mono">${node.roleLabel || node.role}</p>
              <div class="mt-1 h-1 w-full bg-bg-primary rounded-full overflow-hidden">
                <div class="h-full bg-accent" style="width: ${node.activity}%"></div>
              </div>
              <p class="text-[8px] text-text-muted mt-1">影响力: ${node.influence ?? node.val * 4}</p>
            </div>
          `}
        nodeColor="color"
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        linkCurvature={0.25}
        linkColor={(link: any) => link.color}
        linkWidth={(link: any) => link.width}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const label = node.name;
          const fontSize = 12 / globalScale;
          const size = node.val;
          
          // 1. 活跃度脉冲动画
          if (node.activity > 70) {
              const t = Date.now() / 500;
              const pulse = Math.sin(t) * 2 + 2;
              ctx.beginPath();
              ctx.arc(node.x, node.y, size + pulse, 0, 2 * Math.PI, false);
              ctx.fillStyle = `${node.color}33`;
              ctx.fill();
          }

          // 2. 绘制节点主体
          ctx.beginPath(); 
          ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false); 
          ctx.fillStyle = node.color;
          ctx.fill();

          // 3. KOL 特殊标记
          if (node.isKOL) {
              ctx.save();
              ctx.translate(node.x, node.y - size - 2);
              ctx.fillStyle = '#fbbf24';
              ctx.beginPath();
              ctx.moveTo(0, -3);
              ctx.lineTo(2, 0);
              ctx.lineTo(5, 0);
              ctx.lineTo(2, 2);
              ctx.lineTo(3, 5);
              ctx.lineTo(0, 3);
              ctx.lineTo(-3, 5);
              ctx.lineTo(-2, 2);
              ctx.lineTo(-5, 0);
              ctx.lineTo(-2, 0);
              ctx.closePath();
              ctx.fill();
              ctx.restore();
              
              ctx.font = `bold ${8/globalScale}px Sans-Serif`;
              ctx.fillStyle = '#fbbf24';
              ctx.textAlign = 'center';
              ctx.fillText('KOL', node.x, node.y - size - 6/globalScale);
          }

          // 4. 选中标记
          if (node.id === focusId) {
              ctx.strokeStyle = '#fff'; 
              ctx.lineWidth = 2/globalScale; 
              ctx.stroke();
              ctx.shadowBlur = 10;
              ctx.shadowColor = node.color;
          }

          // 5. 名字标签
          if (globalScale > 1.2) {
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#fafafa';
            ctx.fillText(label, node.x, node.y + size + fontSize + 2);
          }
        }}
        onNodeClick={(node: any) => onNodeClick?.(node.id)}
        backgroundColor="#09090b"
      />
      )}
    </div>
  );
}

function getRoleColor(role: string) {
  const colors: any = { 
    KOL: '#f43f5e',
    'AI 乐观派': '#10b981',
    'AI 怀疑派': '#3b82f6',
    'AI 中立派': '#71717a',
    '和平倡导者': '#22c55e',
    '事实核查者': '#f59e0b',
    '中立观察者': '#a1a1aa',
    Evangelist: '#10b981',
    Skeptic: '#3b82f6',
    Observer: '#71717a',
    Neutral: '#a1a1aa'
  };
  return colors[role] || '#71717a';
}

function getActionColor(type: string) {
    const colors: any = {
        'LIKE_POST': '#10b981',
        'FOLLOW': '#3b82f6',
        'REPOST': '#f59e0b',
        'CREATE_COMMENT': '#8b5cf6',
        'CREATE_POST': '#ec4899',
        'interaction': '#8b5cf6'
    };
    return colors[type] || 'rgba(255, 255, 255, 0.2)';
}
