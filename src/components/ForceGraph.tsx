import ForceGraph2D from 'react-force-graph-2d';
import { useMemo, useRef, useEffect, useState } from 'react';
import * as d3 from 'd3';

export function ForceGraph({ agents, onNodeClick, focusId }: any) {
  const fgRef = useRef<any>();
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
    const nodes = agents.map((a: any) => ({
      id: a.id,
      name: a.name || 'Unknown Agent',
      val: Math.max(4, (a.influence || 20) / 4), // 默认影响力 20
      role: a.role || 'Neutral',
      color: getRoleColor(a.role || 'Neutral'),
      activity: a.activity || 0,
      isKOL: a.role === 'KOL'
    }));

    const links: any[] = [];
    
    agents.forEach((a: any) => {
      // 关注关系
      if (a.following && Array.isArray(a.following)) {
        a.following.forEach((targetId: string) => {
          links.push({
            source: a.id,
            target: targetId,
            type: 'follow',
            color: 'rgba(59, 130, 246, 0.2)',
            width: 1
          });
        });
      }

      // 最近互动
      if (a.lastAction?.targetAgentId) {
        links.push({
          source: a.id,
          target: a.lastAction.targetAgentId,
          type: 'interaction',
          actionType: a.lastAction.type,
          color: getActionColor(a.lastAction.type),
          width: 2,
          active: true
        });
      }
    });

    return { nodes, links };
  }, [agents]);

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
              <p class="text-[10px] text-text-tertiary uppercase font-mono">${node.role}</p>
              <div class="mt-1 h-1 w-full bg-bg-primary rounded-full overflow-hidden">
                <div class="h-full bg-accent" style="width: ${node.activity}%"></div>
              </div>
              <p class="text-[8px] text-text-muted mt-1">影响力: ${node.val * 4}</p>
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
        onNodeClick={onNodeClick}
        backgroundColor="#09090b"
      />
      )}
    </div>
  );
}

function getRoleColor(role: string) {
  const colors: any = { 
    KOL: '#f43f5e',
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
        'CREATE_POST': '#ec4899'
    };
    return colors[type] || 'rgba(255, 255, 255, 0.2)';
}
