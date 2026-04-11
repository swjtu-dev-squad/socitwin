import {
  Card,
  ScrollArea,
  Badge,
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell
} from '@/components/ui';
import {
  Terminal,
  Cpu,
  Activity,
  Server,
  Network,
  Clock
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Mock data
const MOCK_AGENTS = Array.from({ length: 12 }, (_, i) => ({
  id: `agent_${i.toString().padStart(3, '0')}`,
  status: i < 2 ? 'BOOTING' : 'ONLINE',
  workingState: i % 3 === 0 ? 'THINKING' : i % 4 === 0 ? 'POSTING' : 'IDLE',
  memoryLength: Math.floor(Math.random() * 5000) + 1000,
  lastActive: new Date(Date.now() - Math.random() * 60000).toLocaleTimeString(),
  cpuUsage: Math.floor(Math.random() * 40) + 10,
}));

const MOCK_KG_LOGS = [
  { time: '10:24:01', action: 'SYNC', detail: 'Synchronized 142 new entities from Reddit stream.' },
  { time: '10:24:05', action: 'EXTRACT', detail: 'Extracted relation: [Agent_003] -> (AGREES_WITH) -> [Topic_AI_Ethics]' },
  { time: '10:24:12', action: 'MERGE', detail: 'Merged duplicate nodes for "GPT-5".' },
  { time: '10:24:18', action: 'INDEX', detail: 'Rebuilding vector index for fast semantic search...' },
];

const MOCK_LLM_LOGS = Array.from({ length: 20 }, (_, i) => ({
  id: i,
  time: new Date(Date.now() - i * 5000).toLocaleTimeString(),
  model: i % 3 === 0 ? 'gpt-4-turbo' : 'claude-3-opus',
  promptTokens: Math.floor(Math.random() * 1000) + 200,
  completionTokens: Math.floor(Math.random() * 500) + 50,
  latency: (Math.random() * 2 + 0.5).toFixed(2),
  status: '200 OK',
  task: i % 2 === 0 ? 'Generate Post' : 'Evaluate Sentiment'
}));

export default function Logs() {
  return (
    <div className="px-6 lg:px-12 py-10 space-y-8 h-full flex flex-col overflow-hidden">
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 shrink-0">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <Terminal className="w-10 h-10 text-accent" />
            系统日志
          </h1>
          <p className="text-text-tertiary mt-1">全栈系统运行状态监控与底层日志追踪</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className="h-9 px-4 border-emerald-500/30 text-emerald-500 bg-emerald-500/10 gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
            SYSTEM ONLINE
          </Badge>
        </div>
      </header>

      <ScrollArea className="flex-1 pr-4 -mr-4 custom-scrollbar">
        <div className="space-y-6 pb-10">
          
          {/* 1. Agent Working Logs */}
          <Card className="bg-bg-secondary border-border-default overflow-hidden">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
              <h2 className="text-sm font-bold flex items-center gap-2 text-text-primary">
                <Cpu className="w-4 h-4 text-accent" />
                智能体工作日志 (Agent Workers)
              </h2>
              <Badge variant="outline" className="text-[10px] border-accent/20 text-accent">
                {MOCK_AGENTS.filter(a => a.status === 'ONLINE').length} / {MOCK_AGENTS.length} ONLINE
              </Badge>
            </div>
            <div className="p-0">
              <Table>
                <TableHeader className="bg-bg-tertiary/30">
                  <TableRow className="border-border-default hover:bg-transparent">
                    <TableHead className="text-xs font-bold text-text-tertiary">Agent ID</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary">启动状态</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary">工作状态</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">记忆长度 (Tokens)</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">CPU 占用</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">最后活跃</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {MOCK_AGENTS.map((agent) => (
                    <TableRow key={agent.id} className="border-border-default hover:bg-bg-tertiary/30">
                      <TableCell className="font-mono text-xs font-bold text-text-secondary">{agent.id}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={cn(
                          "text-[10px] py-0 h-5 border-none",
                          agent.status === 'ONLINE' ? "bg-emerald-500/10 text-emerald-500" : "bg-amber-500/10 text-amber-500"
                        )}>
                          {agent.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {agent.workingState === 'THINKING' && <Activity className="w-3 h-3 text-blue-400 animate-pulse" />}
                          {agent.workingState === 'POSTING' && <Terminal className="w-3 h-3 text-purple-400" />}
                          {agent.workingState === 'IDLE' && <Clock className="w-3 h-3 text-text-muted" />}
                          <span className="text-xs text-text-secondary">{agent.workingState}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-text-tertiary">{agent.memoryLength.toLocaleString()}</TableCell>
                      <TableCell className="text-right font-mono text-xs text-text-tertiary">{agent.cpuUsage}%</TableCell>
                      <TableCell className="text-right font-mono text-xs text-text-tertiary">{agent.lastActive}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>

          {/* 2. Knowledge Graph Status */}
          <Card className="bg-bg-secondary border-border-default overflow-hidden">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
              <h2 className="text-sm font-bold flex items-center gap-2 text-text-primary">
                <Network className="w-4 h-4 text-purple-500" />
                知识图谱库启动和运行状态 (Knowledge Graph)
              </h2>
              <div className="flex gap-4">
                <div className="text-right">
                  <p className="text-[9px] text-text-tertiary uppercase font-bold">Nodes</p>
                  <p className="text-sm font-mono font-bold text-purple-400">14,205</p>
                </div>
                <div className="text-right">
                  <p className="text-[9px] text-text-tertiary uppercase font-bold">Edges</p>
                  <p className="text-sm font-mono font-bold text-purple-400">48,912</p>
                </div>
              </div>
            </div>
            <div className="p-4 bg-black/40 font-mono text-xs space-y-2 h-[200px] overflow-y-auto custom-scrollbar">
              {MOCK_KG_LOGS.map((log, i) => (
                <div key={i} className="flex gap-4 items-start">
                  <span className="text-text-muted shrink-0">{log.time}</span>
                  <span className={cn(
                    "shrink-0 w-16",
                    log.action === 'SYNC' ? "text-blue-400" :
                    log.action === 'EXTRACT' ? "text-emerald-400" :
                    log.action === 'MERGE' ? "text-amber-400" : "text-purple-400"
                  )}>[{log.action}]</span>
                  <span className="text-text-secondary">{log.detail}</span>
                </div>
              ))}
              <div className="flex gap-4 items-start animate-pulse">
                <span className="text-text-muted shrink-0">10:24:22</span>
                <span className="text-accent shrink-0 w-16">[AWAIT]</span>
                <span className="text-text-tertiary">Listening for new entity streams...</span>
              </div>
            </div>
          </Card>

          {/* 3. LLM Logs */}
          <Card className="bg-bg-secondary border-border-default overflow-hidden">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
              <h2 className="text-sm font-bold flex items-center gap-2 text-text-primary">
                <Server className="w-4 h-4 text-emerald-500" />
                大模型启动与运行日志 (LLM Engine)
              </h2>
              <Badge variant="outline" className="text-[10px] border-emerald-500/20 text-emerald-500">
                API HEALTHY
              </Badge>
            </div>
            <div className="p-0">
              <Table>
                <TableHeader className="bg-bg-tertiary/30">
                  <TableRow className="border-border-default hover:bg-transparent">
                    <TableHead className="text-xs font-bold text-text-tertiary w-24">Time</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary">Model</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary">Task</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">Prompt</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">Completion</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">Latency</TableHead>
                    <TableHead className="text-xs font-bold text-text-tertiary text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {MOCK_LLM_LOGS.map((log) => (
                    <TableRow key={log.id} className="border-border-default hover:bg-bg-tertiary/30">
                      <TableCell className="font-mono text-xs text-text-muted">{log.time}</TableCell>
                      <TableCell className="font-mono text-xs text-accent">{log.model}</TableCell>
                      <TableCell className="text-xs text-text-secondary">{log.task}</TableCell>
                      <TableCell className="text-right font-mono text-xs text-text-tertiary">{log.promptTokens}t</TableCell>
                      <TableCell className="text-right font-mono text-xs text-text-tertiary">{log.completionTokens}t</TableCell>
                      <TableCell className="text-right font-mono text-xs text-amber-400">{log.latency}s</TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline" className="text-[9px] py-0 h-5 border-none bg-emerald-500/10 text-emerald-500">
                          {log.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>

        </div>
      </ScrollArea>
    </div>
  );
}
