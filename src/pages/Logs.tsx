import { useState, useMemo, useEffect } from 'react';
import { useSimulationStore } from '@/lib/store';
import { 
  Card,
  Button,
  Input,
  ScrollArea,
  Badge
} from '@/components/ui';
import { 
  MessageSquare, 
  Download, 
  Pause, 
  Play, 
  Search,
  FileText,
  Zap
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

export default function Logs() {
  const { logs, status } = useSimulationStore();
  const [isPaused, setIsPaused] = useState(false);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [displayLogs, setDisplayLogs] = useState(logs);

  // Update display logs only when not paused
  useEffect(() => {
    if (!isPaused) {
      setDisplayLogs(logs);
    }
  }, [logs, isPaused]);

  const filteredLogs = useMemo(() => {
    return displayLogs.filter(log => {
      const matchesSearch = log.agentId.toLowerCase().includes(search.toLowerCase()) || 
                           log.content.toLowerCase().includes(search.toLowerCase());
      const matchesType = filterType === 'ALL' || log.actionType === filterType;
      return matchesSearch && matchesType;
    });
  }, [displayLogs, search, filterType]);

  const handleExportCSV = () => {
    if (logs.length === 0) {
      toast.error("没有可导出的日志");
      return;
    }
    const headers = ['Timestamp', 'AgentID', 'Action', 'Content', 'Reason'];
    const csvRows = logs.map(log => [
      log.timestamp,
      log.agentId,
      log.actionType,
      `"${log.content.replace(/"/g, '""')}"`,
      `"${log.reason.replace(/"/g, '""')}"`
    ].join(','));
    
    const csvContent = [headers.join(','), ...csvRows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `oasis_logs_${new Date().toISOString()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("日志导出成功");
  };

  const actionTypes = ['CREATE_POST', 'LIKE_POST', 'FOLLOW', 'REPORT_POST'];

  return (
    <div className="p-8 h-full flex flex-col space-y-8">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <FileText className="w-10 h-10 text-emerald-500" />
            通信日志
          </h1>
          <p className="text-zinc-500 mt-1">实时监控智能体之间的交互行为与决策逻辑</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <div className="flex items-center gap-2">
              <div className={cn("w-2 h-2 rounded-full", status.running ? "bg-emerald-500 animate-pulse" : "bg-zinc-600")}></div>
              <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest">
                {status.running ? '实时模式' : '已停止'}
              </span>
            </div>
            <p className="text-[10px] text-zinc-600 font-mono mt-0.5">已接收 {logs.length} 条日志 · 1s/次</p>
          </div>
          <Button 
            variant="outline" 
            className="rounded-xl border-zinc-800 h-10 text-xs gap-2"
            onClick={() => setIsPaused(!isPaused)}
          >
            {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            {isPaused ? '恢复滚动' : '暂停滚动'}
          </Button>
          <Button 
            variant="default" 
            className="rounded-xl h-10 text-xs gap-2 bg-emerald-600 hover:bg-emerald-700"
            onClick={handleExportCSV}
          >
            <Download className="w-4 h-4" />
            导出 CSV
          </Button>
        </div>
      </header>

      <Card className="flex-1 bg-zinc-900 border-zinc-800 flex flex-col overflow-hidden">
        <div className="p-6 border-b border-zinc-800 bg-zinc-900/50 flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 min-w-[300px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input 
              placeholder="搜索 Agent ID 或 内容..." 
              className="pl-10 bg-zinc-950 border-zinc-800 h-11 rounded-xl"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              disabled={logs.length === 0}
            />
          </div>
          <div className="flex gap-2">
            <Button 
              variant={filterType === 'ALL' ? 'secondary' : 'outline'} 
              onClick={() => setFilterType('ALL')}
              className="h-11 px-4 rounded-xl text-xs font-bold border-zinc-800"
              disabled={logs.length === 0}
            >全部</Button>
            {actionTypes.map(type => (
              <Button 
                key={type}
                variant={filterType === type ? 'secondary' : 'outline'} 
                onClick={() => setFilterType(type)}
                className="h-11 px-4 rounded-xl text-xs font-bold border-zinc-800"
                disabled={logs.length === 0}
              >
                {type}
              </Button>
            ))}
          </div>
        </div>

        <ScrollArea className="flex-1 p-0">
          {logs.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center p-12 text-center">
              <div className="w-32 h-32 bg-zinc-950 rounded-full flex items-center justify-center mb-8 relative">
                <div className="absolute inset-0 bg-emerald-500/5 animate-ping rounded-full"></div>
                <div className="w-24 h-24 bg-zinc-900 rounded-full flex items-center justify-center border-2 border-dashed border-zinc-800">
                  <MessageSquare className="w-10 h-10 text-zinc-800" />
                </div>
              </div>
              <h3 className="text-xl font-bold text-zinc-300 mb-2">等待日志流输入...</h3>
              <p className="text-sm text-zinc-500 max-w-sm leading-relaxed mb-8">
                启动模拟后，智能体之间的每一条交互、决策和思考逻辑都将实时显示在这里。
              </p>
              <div className="flex gap-4">
                <Link to="/control">
                  <Button className="bg-emerald-600 hover:bg-emerald-700 rounded-xl px-8 h-12 font-bold gap-2">
                    <Zap className="w-4 h-4" />
                    立即前往控制中心启动
                  </Button>
                </Link>
                <Button variant="outline" className="rounded-xl px-8 h-12 border-zinc-800 font-bold">注入测试日志</Button>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {filteredLogs.map((log, i) => (
                <div 
                  key={i} 
                  className="p-4 hover:bg-zinc-800/30 transition-all flex gap-4 group relative animate-in fade-in slide-in-from-bottom-2 duration-300"
                >
                  <div className={cn(
                    "absolute left-0 top-0 bottom-0 w-1",
                    log.actionType === 'CREATE_POST' ? "bg-emerald-500" :
                    log.actionType === 'LIKE_POST' ? "bg-blue-500" :
                    log.actionType === 'FOLLOW' ? "bg-purple-500" : "bg-rose-500"
                  )}></div>
                  <div className="w-20 shrink-0 text-[10px] font-mono text-zinc-500 pt-1">{log.timestamp}</div>
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-emerald-400 font-mono">{log.agentId}</span>
                      <Badge 
                        variant="outline" 
                        className={cn(
                          "text-[9px] py-0 h-5",
                          log.actionType === 'CREATE_POST' ? "text-emerald-400 border-emerald-500/20" :
                          log.actionType === 'LIKE_POST' ? "text-blue-400 border-blue-500/20" :
                          "text-zinc-500 border-zinc-800"
                        )}
                      >
                        {log.actionType}
                      </Badge>
                    </div>
                    <p className="text-sm text-zinc-200 leading-relaxed">{log.content}</p>
                    <div className="flex items-center gap-2 text-[10px] text-zinc-500 italic bg-zinc-950/50 p-2 rounded-lg border border-zinc-800/50 group-hover:border-zinc-700 transition-colors">
                      <span className="text-zinc-600 font-bold uppercase tracking-tighter text-zinc-600">Reason:</span>
                      {log.reason}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </Card>
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
