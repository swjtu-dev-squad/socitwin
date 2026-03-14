import { Agent } from '@/lib/types';

interface ForceGraphProps {
  agents: Agent[];
  onNodeClick: (agent: Agent) => void;
}

export default function ForceGraph({ agents, onNodeClick }: ForceGraphProps) {
  // TODO: Implement graph visualization
  // Neo4j Visualization Library integration pending
  return (
    <div style={{
      width: '100%',
      height: '100%',
      background: '#1a1a1a',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#71717a',
      fontSize: '14px',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ marginBottom: '12px', opacity: 0.5 }}>
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ margin: '0 auto' }}>
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="4" />
            <line x1="12" y1="2" x2="12" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
          </svg>
        </div>
        <div>Graph Visualization</div>
        <div style={{ fontSize: '12px', marginTop: '8px', opacity: 0.7 }}>
          Coming Soon
        </div>
      </div>
    </div>
  );
}
