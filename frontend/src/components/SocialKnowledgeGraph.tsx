import { useEffect, useRef, useMemo, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import * as d3 from 'd3';

interface SocialKnowledgeGraphProps {
  data: any;
}

function escapeHtml(s: string) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** 本地盘状图：``user_type`` 由 ``users.json`` 经 ``buildLocalSocialGraphLayout`` 写入节点；Mongo 生成图可能为 ``userType``。 */
function resolveIsKol(node: any): boolean {
  if (node.type !== 'agent') return false;
  const ut = String(node.user_type ?? node.userType ?? '').toLowerCase();
  return ut === 'kol';
}

export const SocialKnowledgeGraph = ({ data }: SocialKnowledgeGraphProps) => {
  const fgRef = useRef<any>(null);
  const fixedLayout = false;

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };

    const rawNodes = Array.isArray(data.nodes) ? data.nodes : [];
    const normalizedLinks = (Array.isArray(data.edges) ? data.edges : [])
      .map((edge: any) => ({
        ...edge,
        source: typeof edge.source === 'object' ? edge.source?.id : edge.source,
        target: typeof edge.target === 'object' ? edge.target?.id : edge.target,
      }))
      .filter((edge: any) => edge.source && edge.target);

    const nodeIds = new Set(rawNodes.map((node: any) => node.id));
    const links = normalizedLinks.filter((edge: any) => nodeIds.has(edge.source) && nodeIds.has(edge.target));

    const degreeById = new Map<string, number>();
    for (const link of links) {
      degreeById.set(link.source, (degreeById.get(link.source) || 0) + 1);
      degreeById.set(link.target, (degreeById.get(link.target) || 0) + 1);
    }

    const nodes = rawNodes.map((node: any) => {
      const degree = degreeById.get(node.id) || 0;
      const isKol = resolveIsKol(node);
      return {
        ...node,
        degree,
        isKol,
        val: node.type === 'topic' ? 6.5 : 5,
      };
    });

    return { nodes, links };
  }, [data]);

  const configureForces = useCallback(() => {
    const fg = fgRef.current;
    if (!fg || graphData.nodes.length === 0) return;
    try {
      fg.d3Force('homePullX', null);
      fg.d3Force('homePullY', null);
      fg.d3Force('center', d3.forceCenter(0, 0));
      if (typeof fg.d3VelocityDecay === 'function') {
        fg.d3VelocityDecay(0.35);
      }
      if (typeof fg.d3AlphaDecay === 'function') {
        fg.d3AlphaDecay(0.05);
      }
      fg.d3Force('charge')?.strength(-140);
      const linkFree = fg.d3Force('link');
      linkFree
        ?.distance((link: any) => (link.type === 'topic_link' ? 88 : 108))
        ?.strength((link: any) => (link.type === 'topic_link' ? 0.5 : 0.82));
      fg.d3ReheatSimulation?.();
      if (typeof fg.d3Alpha === 'function') {
        fg.d3Alpha(1);
      }
    } catch (e) {
      console.error('SocialKnowledgeGraph: configure forces failed', e);
    }
  }, [graphData.nodes.length, graphData.links.length, fixedLayout]);

  useEffect(() => {
    configureForces();
    const timer = window.setTimeout(() => {
      fgRef.current?.zoomToFit?.(700, 80);
    }, 320);
    return () => window.clearTimeout(timer);
  }, [graphData, fixedLayout, configureForces]);

  return (
    <div className="w-full h-full bg-bg-primary/30">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        enableNodeDrag={!fixedLayout}
        cooldownTicks={fixedLayout ? 420 : 120}
        nodePointerAreaPaint={(node: any, color, ctx) => {
          const r = (node.val || 5) + 4;
          const px = typeof node.x === 'number' && Number.isFinite(node.x) ? node.x : 0;
          const py = typeof node.y === 'number' && Number.isFinite(node.y) ? node.y : 0;
          ctx.beginPath();
          ctx.arc(px, py, r, 0, 2 * Math.PI, false);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        nodeLabel={(node: any) => {
          if (node.type === 'topic') {
            return `
              <div class="bg-bg-secondary border border-rose-500/30 p-2 rounded-lg shadow-xl text-[10px] max-w-[280px]">
                <div class="font-bold text-rose-500 mb-1">话题: ${escapeHtml(node.name)}</div>
                <div class="text-text-secondary italic">实时热度: ${node.heat || 'High'}</div>
                <div class="mt-1 text-[8px] text-text-tertiary">订阅源: ${node.source || 'Live-Link'}</div>
              </div>
            `;
          }
          const badge = node.isKol ? '<span class="text-amber-400 font-bold">KOL</span> · ' : '';
          const bio = escapeHtml(node.bio || '');
          const interests = Array.isArray(node.interests)
            ? node.interests
                .slice(0, 10)
                .map((i: string) => `<span class="bg-bg-tertiary px-1 rounded text-[8px]">${escapeHtml(i)}</span>`)
                .join('')
            : '';
          return `
            <div class="bg-bg-secondary border border-border-default p-2 rounded-lg shadow-xl text-[10px] max-w-[260px]">
              <div class="font-bold text-accent mb-1">${badge}${escapeHtml(String(node.name ?? node.id ?? ''))}</div>
              <div class="text-text-secondary italic line-clamp-4">"${bio}"</div>
              <div class="mt-1 flex flex-wrap gap-1">${interests}</div>
            </div>
          `;
        }}
        nodeRelSize={6}
        nodeColor={(node: any) => {
          if (node.type === 'topic') return '#f43f5e';
          return '#38bdf8';
        }}
        linkColor={(link: any) => {
          if (link.type === 'topic_link') return '#f43f5e';
          return '#38bdf8';
        }}
        linkWidth={(link: any) => (link.type === 'topic_link' ? 2.2 : 1.85)}
        linkLineDash={() => []}
        backgroundColor="transparent"
        onNodeClick={(node: any) => {
          console.log('Clicked node:', node);
        }}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const label = String(node.name ?? node.id ?? '');
          const r = node.val ?? 5;
          const nx = typeof node.x === 'number' && Number.isFinite(node.x) ? node.x : 0;
          const ny = typeof node.y === 'number' && Number.isFinite(node.y) ? node.y : 0;

          ctx.beginPath();
          ctx.arc(nx, ny, r, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.type === 'topic' ? '#f43f5e' : '#38bdf8';
          ctx.fill();
          ctx.strokeStyle = '#0f172a';
          ctx.lineWidth = 1.2 / globalScale;
          ctx.stroke();

          if (node.isKol) {
            const fontSize = Math.max(5.5, 6.8 / globalScale);
            ctx.font = `${fontSize}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillStyle = '#cbd5e1';
            const short = label.length > 14 ? `${label.slice(0, 12)}…` : label;
            ctx.fillText(short, nx, ny + r + 2);
          }
        }}
      />
    </div>
  );
};
