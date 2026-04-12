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
          following: agent.following || [],
          followerCount: agent.followerCount || 0,
          followingCount: agent.followingCount || 0,
          interactionCount: agent.interactionCount || 0,
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
        val: Math.max(8, Math.round((node.influence || 0) * 50) || 8), // 基于影响力调整节点大小
        color: getActivityColor(node.activity || 0), // 基于活跃度的热力图颜色
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
        {/* 颜色图例 */}
        <div className="absolute top-4 right-4 bg-black/40 backdrop-blur-sm rounded-lg border border-white/10 px-3 py-2">
          <div className="text-[10px] text-white/70 mb-2">活跃度热力图</div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded-full" style={{background: '#1e3a8a'}}></div>
            <div className="w-3 h-3 rounded-full" style={{background: '#3b82f6'}}></div>
            <div className="w-3 h-3 rounded-full" style={{background: '#06b6d4'}}></div>
            <div className="w-3 h-3 rounded-full" style={{background: '#f59e0b'}}></div>
            <div className="w-3 h-3 rounded-full" style={{background: '#ef4444'}}></div>
          </div>
          <div className="flex justify-between text-[8px] text-white/50 mt-1">
            <span>不活跃</span>
            <span>活跃</span>
          </div>
          <div className="text-[9px] text-white/60 mt-2">
            节点大小 = 影响力
          </div>
        </div>

        {graphData.nodes.map((node: any, index: number) => {
          const angle = (Math.PI * 2 * index) / Math.max(graphData.nodes.length, 1) - Math.PI / 2;
          const x = centerX + Math.cos(angle) * radius;
          const y = centerY + Math.sin(angle) * radius;
          const size = Math.max(18, node.val * 2.2);
          const selected = node.id === focusId;

          return (
            <div
              key={node.id}
              className="absolute -translate-x-1/2 -translate-y-1/2 group"
              style={{ left: x, top: y }}
            >
              <button
                type="button"
                onClick={() => onNodeClick?.(node.id)}
                className="block"
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
              </button>
              {/* Hover 时显示的详细信息 - 位于节点上方 */}
              <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none mb-3 min-w-[140px] -translate-x-1/3 -translate-y-full rounded-xl border border-white/8 bg-black/40 px-3 py-2 backdrop-blur-sm">
                <p className="text-xs font-semibold text-white">{node.name}</p>
                <div className="mt-1.5 space-y-0.5 text-[10px] text-white/70">
                  <div className="flex justify-between gap-2">
                    <span>影响力</span>
                    <span className="font-semibold text-white">{(node.influence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span>活跃度</span>
                    <span className="font-semibold" style={{color: getActivityColor(node.activity)}}>
                      {node.activity.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span>粉丝</span>
                    <span className="font-semibold text-white">{node.followerCount || 0}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full min-h-0 flex items-center justify-center relative">
      {/* 颜色图例 */}
      <div className="absolute top-4 right-4 z-10 bg-black/40 backdrop-blur-sm rounded-lg border border-white/10 px-3 py-2">
        <div className="text-[10px] text-white/70 mb-2">活跃度热力图</div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded-full" style={{background: '#1e3a8a'}}></div>
          <div className="w-3 h-3 rounded-full" style={{background: '#3b82f6'}}></div>
          <div className="w-3 h-3 rounded-full" style={{background: '#06b6d4'}}></div>
          <div className="w-3 h-3 rounded-full" style={{background: '#f59e0b'}}></div>
          <div className="w-3 h-3 rounded-full" style={{background: '#ef4444'}}></div>
        </div>
        <div className="flex justify-between text-[8px] text-white/50 mt-1">
          <span>不活跃</span>
          <span>活跃</span>
        </div>
        <div className="text-[9px] text-white/60 mt-2">
          节点大小 = 影响力
        </div>
      </div>

      {dimensions.width > 0 && (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          cooldownTicks={100}
          nodeRelSize={1}
          nodeLabel={(node: any) => `
            <div style="position: absolute; transform: translate(-50%, -100%); margin-bottom: 12px; white-space: nowrap;" class="bg-bg-secondary p-3 rounded-lg border border-border-default shadow-xl text-text-primary min-w-[180px]">
              <p class="font-bold text-accent text-sm mb-2">${node.name}</p>
              <div class="space-y-1.5">
                <div class="flex justify-between items-center text-xs">
                  <span class="text-text-muted">影响力</span>
                  <span class="font-semibold text-text-primary">${(node.influence * 100).toFixed(0)}%</span>
                </div>
                <div class="flex justify-between items-center text-xs">
                  <span class="text-text-muted">活跃度</span>
                  <span class="font-semibold" style="color: ${getActivityColor(node.activity)}">${node.activity.toFixed(1)}%</span>
                </div>
                <div class="flex justify-between items-center text-xs">
                  <span class="text-text-muted">关注</span>
                  <span class="font-semibold text-text-primary">${node.followingCount || 0}</span>
                </div>
                <div class="flex justify-between items-center text-xs">
                  <span class="text-text-muted">粉丝</span>
                  <span class="font-semibold text-text-primary">${node.followerCount || 0}</span>
                </div>
                <div class="flex justify-between items-center text-xs">
                  <span class="text-text-muted">交互</span>
                  <span class="font-semibold text-text-primary">${node.interactionCount || 0}</span>
                </div>
              </div>
            </div>
          `}
          nodeCanvasObject={(node: any, ctx, globalScale) => {
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

          // 3. 选中标记
          if (node.id === focusId) {
              ctx.strokeStyle = '#fff'; 
              ctx.lineWidth = 2/globalScale; 
              ctx.stroke();
              ctx.shadowBlur = 10;
              ctx.shadowColor = node.color;
          }

        }}
        onNodeClick={(node: any) => onNodeClick?.(node.id)}
        backgroundColor="#09090b"
      />
      )}
    </div>
  );
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

/**
 * 根据活跃度生成热力图颜色
 * 0% (不活跃) -> 蓝色
 * 50% (中等) -> 紫色
 * 100% (活跃) -> 红色
 */
function getActivityColor(activity: number): string {
    // 限制范围在 0-100
    const normalizedActivity = Math.max(0, Math.min(100, activity));

    if (normalizedActivity < 25) {
        // 0-25%: 深蓝 -> 浅蓝
      return interpolateColor('#1e3a8a', '#3b82f6', normalizedActivity / 25);
    } else if (normalizedActivity < 50) {
        // 25-50%: 浅蓝 -> 青色
        return interpolateColor('#3b82f6', '#06b6d4', (normalizedActivity - 25) / 25);
    } else if (normalizedActivity < 75) {
        // 50-75%: 青色 -> 橙色
        return interpolateColor('#06b6d4', '#f59e0b', (normalizedActivity - 50) / 25);
    } else {
        // 75-100%: 橙色 -> 红色
        return interpolateColor('#f59e0b', '#ef4444', (normalizedActivity - 75) / 25);
    }
}

/**
 * 在两个颜色之间插值
 */
function interpolateColor(color1: string, color2: string, factor: number): string {
    const result = color1.slice(1).match(/.{2}/g)?.map((hex, i) => {
        const start = parseInt(hex, 16);
        const end = parseInt(color2.slice(1).match(/.{2}/g)![i], 16);
        const value = Math.round(start + (end - start) * factor);
        return value.toString(16).padStart(2, '0');
    });
    return `#${result?.join('') || color1}`;
}
