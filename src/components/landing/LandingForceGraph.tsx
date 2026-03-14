import { useMemo } from 'react';
import ForceGraph from '@/components/ForceGraph';
import { Agent } from '@/lib/types';

// Mock 数据：社交网络节点
const mockAgents: Agent[] = [
  { id: '1', name: 'Alice', bio: 'AI Researcher', interests: ['Tech', 'Science'], status: 'active' },
  { id: '2', name: 'Bob', bio: 'Data Scientist', interests: ['Data', 'ML'], status: 'active' },
  { id: '3', name: 'Charlie', bio: 'Developer', interests: ['Code', 'AI'], status: 'active' },
  { id: '4', name: 'Diana', bio: 'Product Manager', interests: ['Product', 'Strategy'], status: 'active' },
  { id: '5', name: 'Eve', bio: 'UX Designer', interests: ['Design', 'User'], status: 'thinking' },
  { id: '6', name: 'Frank', bio: 'DevOps Engineer', interests: ['Cloud', 'Infra'], status: 'active' },
  { id: '7', name: 'Grace', bio: 'ML Engineer', interests: ['ML', 'Models'], status: 'active' },
  { id: '8', name: 'Henry', bio: 'Frontend Dev', interests: ['React', 'UI'], status: 'idle' },
  { id: '9', name: 'Iris', bio: 'Backend Dev', interests: ['API', 'Database'], status: 'active' },
  { id: '10', name: 'Jack', bio: 'Security Expert', interests: ['Security', 'Privacy'], status: 'thinking' },
  { id: '11', name: 'Kate', bio: 'Data Analyst', interests: ['Analytics', 'BI'], status: 'active' },
  { id: '12', name: 'Leo', bio: 'Tech Lead', interests: ['Leadership', 'Architecture'], status: 'active' },
  { id: '13', name: 'Mia', bio: 'QA Engineer', interests: ['Testing', 'Quality'], status: 'idle' },
  { id: '14', name: 'Noah', bio: 'Researcher', interests: ['NLP', 'LLM'], status: 'active' },
  { id: '15', name: 'Olivia', bio: 'Consultant', interests: ['Strategy', 'AI'], status: 'active' },
  { id: '16', name: 'Peter', bio: 'Engineer', interests: ['Robotics', 'Automation'], status: 'thinking' },
  { id: '17', name: 'Quinn', bio: 'Data Scientist', interests: ['Stats', 'Research'], status: 'active' },
  { id: '18', name: 'Rachel', bio: 'Product Owner', interests: ['Agile', 'Product'], status: 'active' },
];

interface LandingForceGraphProps {
  onNodeClick?: (agent: Agent) => void;
}

export default function LandingForceGraph({ onNodeClick }: LandingForceGraphProps) {
  const handleNodeClick = (agent: Agent) => {
    if (onNodeClick) {
      onNodeClick(agent);
    } else {
      // 默认行为：在控制台打印
      console.log('Node clicked:', agent);
    }
  };

  return (
    <div className="w-full h-full">
      <ForceGraph agents={mockAgents} onNodeClick={handleNodeClick} />
    </div>
  );
}
