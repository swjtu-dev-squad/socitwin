import { useRef, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Agent } from '@/lib/types';

interface ForceGraphProps {
  agents: Agent[];
  onNodeClick: (agent: Agent) => void;
}

export default function ForceGraph({ agents, onNodeClick }: ForceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const graphData = useMemo(() => {
    const nodes = agents.map(a => ({
      id: a.id,
      name: a.name,
      val: a.status === 'active' ? 10 : 5,
      color: a.status === 'active' ? '#10b981' : '#3f3f46'
    }));

    const links = Array.from({ length: agents.length * 1.5 }, () => ({
      source: agents[Math.floor(Math.random() * agents.length)].id,
      target: agents[Math.floor(Math.random() * agents.length)].id
    })).filter(l => l.source !== l.target);

    return { nodes, links };
  }, [agents]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph2D
        graphData={graphData}
        nodeLabel="name"
        nodeColor={node => (node as any).color}
        nodeRelSize={6}
        linkColor={() => '#27272a'}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        onNodeClick={(node) => onNodeClick(agents.find(a => a.id === node.id)!)}
        backgroundColor="transparent"
        width={900}
        height={600}
      />
    </div>
  );
}

import { useMemo } from 'react';
