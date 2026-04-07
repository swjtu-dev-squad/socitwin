import { useEffect, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface SocialKnowledgeGraphProps {
  data: any;
}

export const SocialKnowledgeGraph = ({ data }: SocialKnowledgeGraphProps) => {
  const fgRef = useRef<any>();

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };

    const normalizedLinks = (Array.isArray(data.edges) ? data.edges : [])
      .map((edge: any) => ({
        ...edge,
        source: typeof edge.source === 'object' ? edge.source?.id : edge.source,
        target: typeof edge.target === 'object' ? edge.target?.id : edge.target,
      }))
      .filter((edge: any) => edge.source && edge.target);

    const nodeIds = new Set((Array.isArray(data.nodes) ? data.nodes : []).map((node: any) => node.id));
    const links = normalizedLinks.filter((edge: any) => nodeIds.has(edge.source) && nodeIds.has(edge.target));

    const degreeById = new Map<string, number>();
    for (const link of links) {
      degreeById.set(link.source, (degreeById.get(link.source) || 0) + 1);
      degreeById.set(link.target, (degreeById.get(link.target) || 0) + 1);
    }

    const nodes = data.nodes.map((node: any) => {
      const degree = degreeById.get(node.id) || 0;
      return {
        ...node,
        degree,
        val: node.type === 'topic' ? 6 : 5,
      };
    });

    return { nodes, links };
  }, [data]);

  useEffect(() => {
    if (fgRef.current && graphData.nodes.length > 0) {
      fgRef.current.d3Force('charge').strength(-68);
      fgRef.current
        .d3Force('link')
        .distance((link: any) => (link.type === 'topic_link' ? 54 : 72))
        .strength((link: any) => (link.type === 'topic_link' ? 0.7 : 0.95));
      fgRef.current.d3ReheatSimulation?.();
      const timer = window.setTimeout(() => {
        fgRef.current?.zoomToFit?.(600, 50);
      }, 250);
      return () => window.clearTimeout(timer);
    }
  }, [graphData]);

  return (
    <div className="w-full h-full bg-bg-primary/30">
      <ForceGraph2D
        ref={fgRef}
        graphData={graphData}
        nodeLabel={(node: any) => {
          if (node.type === 'topic') {
            return `
              <div class="bg-bg-secondary border border-rose-500/30 p-2 rounded-lg shadow-xl text-[10px]">
                <div class="font-bold text-rose-500 mb-1">话题: ${node.name}</div>
                <div class="text-text-secondary italic">实时热度: ${node.heat || 'High'}</div>
                <div class="mt-1 text-[8px] text-text-tertiary">订阅源: ${node.source || 'Live-Link'}</div>
              </div>
            `;
          }
          return `
            <div class="bg-bg-secondary border border-border-default p-2 rounded-lg shadow-xl text-[10px]">
              <div class="font-bold text-accent mb-1">${node.name}</div>
              <div class="text-text-secondary italic">"${node.bio}"</div>
              <div class="mt-1 flex gap-1">
                ${node.interests?.map((i: string) => `<span class="bg-bg-tertiary px-1 rounded text-[8px]">${i}</span>`).join('')}
              </div>
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
          if (link.origin === 'real') return '#38bdf8';
          if (link.origin === 'synthetic') return '#f59e0b';
          return '#64748b';
        }}
        linkWidth={(link: any) => (link.type === 'topic_link' ? 2.2 : link.origin === 'real' ? 1.9 : 1.4)}
        linkLineDash={(link: any) => (link.origin === 'synthetic' ? [4, 3] : [])}
        backgroundColor="transparent"
        cooldownTicks={100}
        onNodeClick={(node: any) => {
          console.log('Clicked node:', node);
        }}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const label = node.name || node.id;
          const fontSize = Math.max(8, 11 / globalScale);
          ctx.font = `${fontSize}px sans-serif`;

          const r = node.val;
          
          if (node.type === 'topic') {
            ctx.fillStyle = '#f43f5e';
            ctx.fillRect(node.x - r, node.y - r, r * 2, r * 2);
            ctx.strokeStyle = '#fb7185';
            ctx.lineWidth = 2 / globalScale;
            ctx.strokeRect(node.x - r, node.y - r, r * 2, r * 2);
          } else {
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
            ctx.fillStyle = '#38bdf8';
            ctx.fill();
            ctx.strokeStyle = '#0f172a';
            ctx.lineWidth = 1.2 / globalScale;
            ctx.stroke();
          }

          if (globalScale > 1.2) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillStyle = '#fafafa';
            ctx.fillText(label, node.x, node.y + r + 2);
          }
        }}
      />
    </div>
  );
};
