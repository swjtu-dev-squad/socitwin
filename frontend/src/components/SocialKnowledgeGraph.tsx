import { useEffect, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface SocialKnowledgeGraphProps {
  data: any;
}

export const SocialKnowledgeGraph = ({ data }: SocialKnowledgeGraphProps) => {
  const fgRef = useRef<any>(undefined);

  const graphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    
    // Ensure nodes have degree centrality for coloring
    const nodes = data.nodes.map((node: any) => {
      const degree = data.edges.filter((e: any) => e.source === node.id || e.target === node.id).length;
      return {
        ...node,
        degree,
        val: 1 + degree * 0.5 // Size based on degree
      };
    });

    return { nodes, links: data.edges };
  }, [data]);

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('charge').strength(-120);
      fgRef.current.d3Force('link').distance(60);
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
          // Color depth based on degree centrality
          const intensity = Math.min(node.degree * 20 + 40, 100);
          return `hsl(217, 91%, ${100 - intensity}%)`; // Blue scale
        }}
        linkColor={(link: any) => {
          if (link.type === 'topic_link') return '#f43f5e';
          return link.type === 'follow' ? '#3b82f6' : '#52525b';
        }}
        linkWidth={(link: any) => (link.type === 'follow' || link.type === 'topic_link' ? 2 : 1)}
        linkLineDash={(link: any) => (link.type === 'interest' ? [2, 2] : [])}
        backgroundColor="transparent"
        onNodeClick={(node: any) => {
          console.log('Clicked node:', node);
        }}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const label = node.name;
          const fontSize = 10 / globalScale;
          ctx.font = `${fontSize}px Inter`;
          
          const r = node.val * 2;
          
          if (node.type === 'topic') {
            // Draw square for topics
            ctx.fillStyle = '#f43f5e';
            ctx.fillRect(node.x - r, node.y - r, r * 2, r * 2);
            ctx.strokeStyle = '#fb7185';
            ctx.lineWidth = 2 / globalScale;
            ctx.strokeRect(node.x - r, node.y - r, r * 2, r * 2);
          } else {
            // Draw node circle for users
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
            
            // Gradient for "social heat"
            const intensity = Math.min(node.degree * 20 + 40, 100);
            ctx.fillStyle = `hsl(217, 91%, ${100 - intensity}%)`;
            ctx.fill();
            
            // Border
            ctx.strokeStyle = '#3b82f6';
            ctx.lineWidth = 1 / globalScale;
            ctx.stroke();
          }

          // Label
          if (globalScale > 1.5) {
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#fafafa';
            ctx.fillText(label, node.x, node.y + r + fontSize);
          }
        }}
      />
    </div>
  );
};
