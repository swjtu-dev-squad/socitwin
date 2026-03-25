import { useState, useMemo, useEffect } from 'react';
import { useSimulationStore } from '@/lib/store';
import { ForceGraph } from '@/components/ForceGraph';
import { AgentBehaviorTable } from '@/components/AgentBehaviorTable';
import { AgentDeepMonitor } from '@/components/AgentDeepMonitor';
import { Card, Button, Badge, Input } from '@/components/ui';
import { Network, List, Activity, Search } from 'lucide-react';

export default function SocialNetworkMonitor() {
  const { status } = useSimulationStore();
  const [viewMode, setViewMode] = useState<'topology' | 'list'>('topology');
  const [selectedAgent, setSelectedAgent] = useState<any>(null);
  const [search, setSearch] = useState('');

  const filteredAgents = useMemo(() => {
    const agents = status.agents || [];
    return agents.filter(a => 
      a.id.toLowerCase().includes(search.toLowerCase()) ||
      a.name.toLowerCase().includes(search.toLowerCase())
    );
  }, [status.agents, search]);

  // 默认选中影响力最大的 Agent
  useEffect(() => {
    if (filteredAgents.length > 0 && !selectedAgent) {
      const topAgent = [...filteredAgents].sort((a, b) => (b.influence || 0) - (a.influence || 0))[0];
      setSelectedAgent(topAgent);
    }
  }, [filteredAgents, selectedAgent]);

  return (
    <div className="px-6 py-8 h-full flex flex-col space-y-6 overflow-hidden">
      {/* 顶部：当前仿真话题上下文 */}
      <header className="flex justify-between items-center bg-bg-secondary p-6 rounded-2xl border border-border-default shrink-0">
        <div className="flex items-center gap-6">
          <div className="p-3 bg-accent/10 rounded-xl">
            <Network className="w-8 h-8 text-accent" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">实时社交网络监控</h1>
            <div className="flex items-center gap-3 mt-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-tertiary uppercase font-bold">仿真平台:</span>
                <Badge className="bg-emerald-500/20 text-emerald-400 border-emerald-500/30">
                  {status.platform || '未定义平台'}
                </Badge>
              </div>
              <div className="w-px h-4 bg-border-default"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-tertiary uppercase font-bold">当前话题:</span>
                <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                  {status.topics?.[0] || '未定义话题'}
                </Badge>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex gap-8 px-6 border-l border-border-default">
          <StatMini label="群体极化率" value={`${(status.polarization * 100).toFixed(1)}%`} color="text-rose-500" />
          <StatMini label="信息传播速度" value={`${(status.velocity || 12.4).toFixed(1)} msg/s`} color="text-emerald-500" />
          <StatMini label="从众效应指数" value={`${((status.herdHhi || 0.24) * 100).toFixed(1)}%`} color="text-blue-500" />
        </div>
      </header>

      {/* 主展示区 */}
      <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden min-h-0">
        <div className="col-span-12 lg:col-span-9 flex flex-col space-y-6 overflow-hidden min-h-0">
          {/* 影响力拓扑图 */}
          <Card className="flex-1 min-h-0 bg-bg-secondary border-border-default flex flex-col overflow-hidden relative">
            <div className="p-4 border-b border-border-default flex justify-between items-center shrink-0">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-accent"/>
                <span className="text-sm font-bold uppercase tracking-wider">影响力拓扑图</span>
              </div>
              <div className="relative w-64">
                 <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
                 <Input 
                   placeholder="搜索特定 Agent..." 
                   className="pl-9 h-9 bg-bg-primary" 
                   value={search}
                   onChange={(e) => setSearch(e.target.value)}
                 />
              </div>
            </div>
            <div className="flex-1 relative overflow-hidden bg-black/20">
              <ForceGraph 
                agents={filteredAgents} 
                onNodeClick={setSelectedAgent}
                focusId={selectedAgent?.id}
              />
            </div>
          </Card>

          {/* 行为列表 - 放在下面并带滚动条 */}
          <Card className="flex-1 min-h-0 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
            <div className="p-4 border-b border-border-default flex items-center gap-2 shrink-0">
              <List className="w-4 h-4 text-blue-400"/>
              <span className="text-sm font-bold uppercase tracking-wider">Agent 行为动态列表</span>
            </div>
            <div className="flex-1 min-h-0">
              <AgentBehaviorTable agents={filteredAgents} onSelect={setSelectedAgent} selectedId={selectedAgent?.id} />
            </div>
          </Card>
        </div>

        {/* 右侧：选中 Agent 的深度监控 */}
        <Card className="hidden lg:flex col-span-3 bg-bg-secondary border-border-default p-6 flex-col space-y-6 overflow-auto custom-scrollbar">
          {selectedAgent ? (
            <AgentDeepMonitor agent={selectedAgent} />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-text-muted text-center italic">
              <Activity className="w-12 h-12 mb-4 opacity-10" />
              <p className="text-sm">在左侧选择一个 Agent<br/>以开启深度社交监控</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

function StatMini({ label, value, color }: any) {
  return (
    <div className="text-center">
      <p className="text-[10px] font-bold text-text-tertiary uppercase tracking-tighter">{label}</p>
      <p className={`text-xl font-mono font-bold ${color}`}>{value}</p>
    </div>
  );
}
