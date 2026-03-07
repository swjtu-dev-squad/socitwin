import { useState, useMemo } from 'react';
import { useSimulationStore } from '@/lib/store';
import ForceGraph from '@/components/ForceGraph';
import AgentDetailDrawer from '@/components/AgentDetailDrawer';
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow,
  Input,
  Card,
  Button,
  Badge,
  ScrollArea
} from '@/components/ui';
import { 
  Users, 
  Search, 
  Filter, 
  Maximize2, 
  RefreshCw, 
  Share2, 
  Settings2,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { Agent } from '@/lib/types';
import { Link } from 'react-router-dom';

export default function Agents() {
  const { status } = useSimulationStore();
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<'ALL' | 'ACTIVE' | 'IDLE'>('ALL');

  const filteredAgents = useMemo(() => {
    return status.agents.filter(a => {
      const matchesSearch = a.id.toLowerCase().includes(search.toLowerCase()) || 
                           a.name.toLowerCase().includes(search.toLowerCase());
      const matchesFilter = filter === 'ALL' || 
                           (filter === 'ACTIVE' && a.status === 'active') || 
                           (filter === 'IDLE' && a.status === 'idle');
      return matchesSearch && matchesFilter;
    });
  }, [status.agents, search, filter]);

  return (
    <div className="p-8 h-full flex flex-col space-y-8">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <Users className="w-10 h-10 text-emerald-500" />
            智能体监控
          </h1>
          <p className="text-zinc-500 mt-1">实时观察 Agent 社交行为与网络演化</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded-xl">
            <div className={cn(
              "w-2 h-2 rounded-full",
              status.running && !status.paused ? "bg-emerald-500 animate-pulse" :
              status.paused ? "bg-amber-500" : "bg-zinc-600"
            )}></div>
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">
              {status.running && !status.paused ? '实时更新中 (每 3s)' : status.paused ? '已暂停' : '引擎已停止'}
            </span>
          </div>
          <Link to="/control">
            <Button variant="outline" className="rounded-xl border-zinc-800 h-10 text-xs gap-2">
              <Settings2 className="w-4 h-4" />
              配置引擎
            </Button>
          </Link>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1 min-h-0">
        {/* Network Graph */}
        <Card className="lg:col-span-7 bg-zinc-900 border-zinc-800 relative overflow-hidden flex flex-col">
          <div className="p-4 border-b border-zinc-800 bg-zinc-900/50 flex justify-between items-center relative z-10">
            <div className="flex items-center gap-4">
              <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-500">社交拓扑网络</h2>
              <div className="flex items-center gap-3 text-[10px] font-bold">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]"></div>
                  <span className="text-zinc-400">活跃 (Active)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-zinc-600"></div>
                  <span className="text-zinc-400">空闲 (Idle)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]"></div>
                  <span className="text-zinc-400">高极化 (Polarized)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                  <span className="text-zinc-400">思考中 (Thinking)</span>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="h-8 w-8 p-0 rounded-lg border-zinc-800"><Maximize2 className="w-3.5 h-3.5" /></Button>
              <Button variant="outline" className="h-8 w-8 p-0 rounded-lg border-zinc-800"><RefreshCw className="w-3.5 h-3.5" /></Button>
            </div>
          </div>
          
          <div className="flex-1 relative bg-zinc-950/50">
            {status.agents.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-12 text-center">
                <div className="w-24 h-24 bg-zinc-900 rounded-full flex items-center justify-center mb-6 opacity-20 border-2 border-dashed border-emerald-500">
                  <Share2 className="w-10 h-10 text-emerald-500" />
                </div>
                <h3 className="text-lg font-bold text-zinc-400 mb-2">社交网络拓扑待初始化</h3>
                <p className="text-xs text-zinc-600 max-w-xs mb-6">启动模拟后，系统将实时绘制 Agent 之间的关注、互动与信息流转关系图谱。</p>
                <Link to="/control">
                  <Button className="bg-emerald-600 hover:bg-emerald-700 rounded-xl px-6">立即前往控制中心启动</Button>
                </Link>
              </div>
            ) : (
              <ForceGraph 
                agents={status.agents} 
                onNodeClick={(node) => setSelectedAgent(node)} 
              />
            )}
          </div>
        </Card>

        {/* Agent List */}
        <Card className="lg:col-span-5 bg-zinc-900 border-zinc-800 flex flex-col overflow-hidden">
          <div className="p-6 border-b border-zinc-800 space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-bold uppercase tracking-widest text-zinc-500">
                智能体列表 
                <span className="ml-2 text-zinc-700 font-mono">({status.activeAgents.toLocaleString()})</span>
              </h2>
              <div className="flex gap-2">
                <Button 
                  variant={filter === 'ALL' ? 'secondary' : 'outline'} 
                  onClick={() => setFilter('ALL')}
                  className="h-7 text-[10px] px-2 rounded-lg"
                >全部</Button>
                <Button 
                  variant={filter === 'ACTIVE' ? 'secondary' : 'outline'} 
                  onClick={() => setFilter('ACTIVE')}
                  className="h-7 text-[10px] px-2 rounded-lg"
                >活跃</Button>
              </div>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
              <Input 
                placeholder="搜索 ID 或 姓名..." 
                className="pl-10 bg-zinc-950 border-zinc-800 h-11 rounded-xl"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <ScrollArea className="flex-1">
            <Table>
              <TableHeader className="bg-zinc-950/30 sticky top-0 z-10">
                <TableRow className="border-zinc-800">
                  <TableHead>Agent</TableHead>
                  <TableHead>最后动作</TableHead>
                  <TableHead className="text-right">极化</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAgents.map((agent) => (
                  <TableRow 
                    key={agent.id} 
                    className={cn(
                      "border-zinc-800 cursor-pointer hover:bg-zinc-800/50 transition-colors group",
                      selectedAgent?.id === agent.id && "bg-emerald-500/5 border-emerald-500/20"
                    )}
                    onClick={() => setSelectedAgent(agent)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-[10px] font-bold text-zinc-500 group-hover:text-emerald-400 transition-colors">
                          {agent.name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-bold text-zinc-200 text-xs">{agent.name}</p>
                          <p className="text-[10px] text-zinc-600 font-mono">{agent.id}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {agent.lastAction ? (
                        <Badge 
                          variant="outline" 
                          className={cn(
                            "text-[9px] py-0 h-5",
                            agent.lastAction.type === 'CREATE_POST' ? "text-emerald-400 border-emerald-500/20 bg-emerald-500/5" :
                            agent.lastAction.type === 'LIKE_POST' ? "text-blue-400 border-blue-500/20 bg-blue-500/5" :
                            "text-rose-400 border-rose-500/20 bg-rose-500/5"
                          )}
                        >
                          {agent.lastAction.type}
                        </Badge>
                      ) : (
                        <span className="text-[10px] text-zinc-700 italic">IDLE</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className={cn(
                        "font-mono text-xs font-bold",
                        (agent as any).polarization > 0.7 ? "text-rose-500" : "text-zinc-500"
                      )}>
                        {(agent as any).polarization?.toFixed(2) || '0.00'}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {filteredAgents.length === 0 && (
              <div className="p-12 text-center text-zinc-600 italic text-sm">
                未找到匹配的智能体
              </div>
            )}
          </ScrollArea>
          
          <div className="p-4 border-t border-zinc-800 bg-zinc-950/50 flex justify-between items-center">
            <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-widest">显示前 50 个结果</span>
            <div className="flex gap-1">
              <Button variant="outline" className="h-7 w-7 p-0 rounded-lg border-zinc-800 disabled:opacity-30" disabled><ChevronLeft className="w-3 h-3" /></Button>
              <Button variant="outline" className="h-7 w-7 p-0 rounded-lg border-zinc-800 disabled:opacity-30" disabled><ChevronRight className="w-3 h-3" /></Button>
            </div>
          </div>
        </Card>
      </div>

      <AgentDetailDrawer 
        agent={selectedAgent} 
        open={!!selectedAgent} 
        onClose={() => setSelectedAgent(null)} 
      />
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
