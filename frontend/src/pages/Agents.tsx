import { useState, useMemo, useEffect, useRef } from 'react';
import { ForceGraph } from '@/components/ForceGraph';
import { AgentBehaviorTable } from '@/components/AgentBehaviorTable';
import { AgentDeepMonitor } from '@/components/AgentDeepMonitor';
import { Card, Badge, Input } from '@/components/ui';
import { Network, List, Search } from 'lucide-react';
import { getAgentDetail, getAgentMonitor } from '@/lib/agentMonitorApi';
import type { AgentDetailResponse, AgentDirtyEvent, AgentMonitorResponse, AgentOverview } from '@/lib/agentMonitorTypes';
import { initSocket } from '@/lib/socket';
import { displayPercentageFormatted, displayMetricFormatted } from '@/lib/safeDisplay';

export default function SocialNetworkMonitor() {
  const [monitor, setMonitor] = useState<AgentMonitorResponse | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<AgentDetailResponse | null>(null);
  const [loadingMonitor, setLoadingMonitor] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const selectedAgentIdRef = useRef<string | null>(null);
  const searchRef = useRef('');
  const monitorRequestId = useRef(0);
  const detailRequestId = useRef(0);

  const filteredAgents = useMemo(() => {
    return filterAgentsBySearch(monitor?.agents || [], search);
  }, [monitor?.agents, search]);

  const graphEdges = useMemo(() => monitor?.graph.edges || [], [monitor?.graph.edges]);

  useEffect(() => {
    selectedAgentIdRef.current = selectedAgentId;
  }, [selectedAgentId]);

  useEffect(() => {
    searchRef.current = search;
  }, [search]);

  async function loadDetail(agentId: string) {
    const requestId = ++detailRequestId.current;
    setLoadingDetail(true);
    setError(null);
    try {
      const detail = await getAgentDetail(agentId);
      if (requestId !== detailRequestId.current) return;
      setSelectedDetail(detail);
    } catch (err: any) {
      if (requestId !== detailRequestId.current) return;
      setSelectedDetail(null);
      setError(err?.message || '加载 detail 失败');
    } finally {
      if (requestId === detailRequestId.current) {
        setLoadingDetail(false);
      }
    }
  }

  async function loadMonitor() {
    const requestId = ++monitorRequestId.current;
    setLoadingMonitor(true);
    setError(null);
    try {
      const data = await getAgentMonitor();
      if (requestId !== monitorRequestId.current) return;
      setMonitor(data);
      const currentSelected = selectedAgentIdRef.current;
      const nextSelected = resolveSelectedAgentId(filterAgentsBySearch(data.agents, searchRef.current), currentSelected);
      if (nextSelected && nextSelected !== currentSelected) {
        setSelectedAgentId(nextSelected);
        setSelectedDetail(null);
        setLoadingDetail(true);
      }
      if (nextSelected) {
        await loadDetail(nextSelected);
      } else {
        setSelectedDetail(null);
      }
    } catch (err: any) {
      if (requestId !== monitorRequestId.current) return;
      setError(err?.message || '加载 monitor 失败');
      setMonitor(null);
      setSelectedDetail(null);
      setSelectedAgentId(null);
    } finally {
      if (requestId === monitorRequestId.current) {
        setLoadingMonitor(false);
      }
    }
  }

  useEffect(() => {
    const socket = initSocket();

    const handleDirty = async (_payload: AgentDirtyEvent) => {
      await loadMonitor();
    };

    socket.on('agents_dirty', handleDirty);
    void loadMonitor();
    const pollId = window.setInterval(() => {
      void loadMonitor();
    }, 5000);

    return () => {
      socket.off('agents_dirty', handleDirty);
      window.clearInterval(pollId);
    };
  }, []);

  useEffect(() => {
    const current = selectedAgentIdRef.current;
    if (!monitor || monitor.agents.length === 0 || current === null) {
      return;
    }

    const nextSelected = resolveSelectedAgentId(filteredAgents, current);
    if (nextSelected && nextSelected !== current) {
      setSelectedAgentId(nextSelected);
      setSelectedDetail(null);
      setLoadingDetail(true);
      void loadDetail(nextSelected);
    }
  }, [filteredAgents, monitor]);

  const handleSelectAgent = (agent: AgentOverview) => {
    setSelectedAgentId(agent.id);
    setSelectedDetail(null);
    setLoadingDetail(true);
    void loadDetail(agent.id);
  };

  const handleNodeClick = (agentId: string) => {
    setSelectedAgentId(agentId);
    setSelectedDetail(null);
    setLoadingDetail(true);
    void loadDetail(agentId);
  };

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
                  {monitor?.simulation.platform || '未定义平台'}
                </Badge>
              </div>
              <div className="w-px h-4 bg-border-default"></div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-tertiary uppercase font-bold">当前话题:</span>
                <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30">
                  {monitor?.simulation.topic || '未定义话题'}
                </Badge>
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex gap-6 px-6 border-l border-border-default">
          <StatMini label="群体极化率" value={displayPercentageFormatted((monitor?.simulation.polarization ?? 0) * 100)} color="text-rose-500" />
          <div className="flex gap-3">
            <StatMini label="传播规模" value={displayMetricFormatted(monitor?.simulation.propagationScale)} color="text-emerald-500" />
            <StatMini label="传播深度" value={displayMetricFormatted(monitor?.simulation.propagationDepth)} color="text-cyan-500" />
            <StatMini label="传播广度" value={displayMetricFormatted(monitor?.simulation.propagationBreadth)} color="text-purple-500" />
          </div>
          <StatMini label="从众效应" value={displayPercentageFormatted((monitor?.simulation.herdIndex ?? 0) * 100)} color="text-blue-500" />
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
                nodes={filteredAgents}
                edges={graphEdges.filter((edge) =>
                  filteredAgents.some((agent) => agent.id === edge.source) &&
                  filteredAgents.some((agent) => agent.id === edge.target)
                )}
                onNodeClick={handleNodeClick}
                focusId={selectedAgentId}
              />
              {loadingMonitor ? (
                <OverlayMessage title="正在加载真实 monitor 数据" description="图谱和列表会在数据返回后自动刷新。" />
              ) : null}
            </div>
          </Card>

          {/* 行为列表 - 放在下面并带滚动条 */}
          <Card className="flex-1 min-h-0 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
            <div className="p-4 border-b border-border-default flex items-center gap-2 shrink-0">
              <List className="w-4 h-4 text-blue-400"/>
              <span className="text-sm font-bold uppercase tracking-wider">Agent 行为动态列表</span>
            </div>
            <div className="flex-1 min-h-0">
              <AgentBehaviorTable agents={filteredAgents} onSelect={handleSelectAgent} selectedId={selectedAgentId} />
            </div>
          </Card>
        </div>

        {/* 右侧：选中 Agent 的深度监控 */}
        <Card className="hidden lg:flex col-span-3 bg-bg-secondary border-border-default p-6 flex-col space-y-6 overflow-auto custom-scrollbar">
          <AgentDeepMonitor detail={selectedDetail} loading={loadingDetail || loadingMonitor} error={error} />
        </Card>
      </div>
    </div>
  );
}

function resolveSelectedAgentId(agents: AgentOverview[], currentSelected: string | null) {
  if (currentSelected && agents.some((agent) => agent.id === currentSelected)) {
    return currentSelected;
  }
  if (agents.length === 0) return null;
  return [...agents]
    .sort((a, b) => (b.influence || 0) - (a.influence || 0) || (b.activity || 0) - (a.activity || 0))[0].id;
}

function filterAgentsBySearch(agents: AgentOverview[], search: string) {
  const query = search.trim().toLowerCase();
  if (!query) return agents;
  return agents.filter((agent) =>
    [agent.id, agent.name, agent.roleLabel, agent.country, agent.city]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  );
}

function OverlayMessage({ title, description }: { title: string; description: string }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-black/45 backdrop-blur-[1px]">
      <div className="rounded-2xl border border-border-default bg-bg-secondary/95 px-5 py-4 text-center shadow-xl">
        <p className="text-sm font-bold text-text-primary">{title}</p>
        <p className="mt-1 text-xs text-text-tertiary">{description}</p>
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
