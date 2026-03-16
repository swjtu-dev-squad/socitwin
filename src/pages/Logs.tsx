import { useState, useMemo, useEffect } from 'react';
import { useSimulationStore } from '@/lib/store';
import { simulationApi } from '@/lib/api';
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
  Zap,
  RefreshCw
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

// 格式化时间戳显示
const formatTimestamp = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(Math.abs(diffMs) / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    // 处理未来时间（时间戳比当前时间快）
    const isFuture = diffMs < 0;
    const suffix = isFuture ? '后' : '前';

    if (diffSecs < 60) {
      return `${diffSecs}秒${suffix}`;
    } else if (diffMins < 60) {
      return `${diffMins}分钟${suffix}`;
    } else if (diffHours < 24) {
      return `${diffHours}小时${suffix}`;
    } else if (diffDays < 7) {
      return `${diffDays}天${suffix}`;
    } else {
      // 超过一周显示完整日期
      return date.toLocaleDateString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    }
  } catch {
    return timestamp;
  }
};

export default function Logs() {
  const { logs, status, setLogs } = useSimulationStore();
  const [isPaused, setIsPaused] = useState(false);
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState('ALL');
  const [displayLogs, setDisplayLogs] = useState(logs);
  const [isLoading, setIsLoading] = useState(false);

  // 从数据库加载历史日志（仅组件挂载时执行一次）
  useEffect(() => {
    const loadLogsFromDatabase = async () => {
      setIsLoading(true);
      try {
        const response = await simulationApi.getLogs();
        if (response.data.logs) {
          setLogs(response.data.logs);
        }
      } catch (error) {
        console.error('Failed to load logs from database:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadLogsFromDatabase();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const handleRefreshLogs = async () => {
    setIsLoading(true);
    try {
      const response = await simulationApi.getLogs();
      if (response.data.logs) {
        setLogs(response.data.logs);
        toast.success(`从数据库加载了 ${response.data.logs.length} 条日志`);
      }
    } catch (error) {
      toast.error("加载日志失败");
      console.error('Failed to refresh logs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const actionTypes = ['CREATE_POST', 'LIKE_POST', 'FOLLOW', 'REPORT_POST'];

  return (
    <div className="px-6 lg:px-12 xl:px-16 py-12 h-full flex flex-col">
      <div className="max-w-7xl mx-auto space-y-8 flex-1 min-h-0">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <FileText className="w-10 h-10 text-accent" />
            通信日志
          </h1>
          <p className="text-text-tertiary mt-1">实时监控智能体之间的交互行为与决策逻辑</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex flex-col items-end">
            <div className="flex items-center gap-2">
              <div className={cn("w-2 h-2 rounded-full",
                status.running && !status.paused ? "bg-accent animate-pulse" :
                status.paused ? "bg-amber-500" : "bg-text-muted"
              )}></div>
              <span className="text-[10px] font-bold text-text-secondary uppercase tracking-widest">
                {status.running && !status.paused ? '实时模式' : status.paused ? '已暂停' : '已停止'}
              </span>
            </div>
            <p className="text-[10px] text-text-muted font-mono mt-0.5">已接收 {logs.length} 条日志 · 1s/次</p>
          </div>
          <Button
            variant="outline"
            className="rounded-xl border-border-default h-10 text-xs gap-2"
            onClick={handleRefreshLogs}
            disabled={isLoading}
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            从数据库刷新
          </Button>
          <Button
            variant="outline"
            className="rounded-xl border-border-default h-10 text-xs gap-2"
            onClick={() => setIsPaused(!isPaused)}
          >
            {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            {isPaused ? '恢复滚动' : '暂停滚动'}
          </Button>
          <Button
            variant="default"
            className="rounded-xl h-10 text-xs gap-2 bg-accent hover:bg-accent-hover"
            onClick={handleExportCSV}
          >
            <Download className="w-4 h-4" />
            导出 CSV
          </Button>
        </div>
      </header>

      <Card className="flex-1 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
        <div className="p-6 border-b border-border-default bg-bg-secondary/50 flex flex-wrap gap-4 items-center">
          <div className="relative flex-1 min-w-[300px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
            <Input 
              placeholder="搜索 Agent ID 或 内容..." 
              className="pl-10 bg-bg-primary border-border-default h-11 rounded-xl"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              disabled={logs.length === 0}
            />
          </div>
          <div className="flex gap-2">
            <Button 
              variant={filterType === 'ALL' ? 'secondary' : 'outline'} 
              onClick={() => setFilterType('ALL')}
              className="h-11 px-4 rounded-xl text-xs font-bold border-border-default"
              disabled={logs.length === 0}
            >全部</Button>
            {actionTypes.map(type => (
              <Button 
                key={type}
                variant={filterType === type ? 'secondary' : 'outline'} 
                onClick={() => setFilterType(type)}
                className="h-11 px-4 rounded-xl text-xs font-bold border-border-default"
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
              <div className="w-32 h-32 bg-bg-primary rounded-full flex items-center justify-center mb-8 relative">
                <div className="absolute inset-0 bg-accent/5 animate-ping rounded-full"></div>
                <div className="w-24 h-24 bg-bg-secondary rounded-full flex items-center justify-center border-2 border-dashed border-border-default">
                  <MessageSquare className="w-10 h-10 text-text-muted" />
                </div>
              </div>
              <h3 className="text-xl font-bold text-text-primary mb-2">等待日志流输入...</h3>
              <p className="text-sm text-text-tertiary max-w-sm leading-relaxed mb-8">
                启动模拟后，智能体之间的每一条交互、决策和思考逻辑都将实时显示在这里。
              </p>
              <div className="flex gap-4">
                <Link to="/overview">
                  <Button className="bg-accent hover:bg-accent-hover rounded-xl px-8 h-12 font-bold gap-2">
                    <Zap className="w-4 h-4" />
                    立即前往概览页启动
                  </Button>
                </Link>
                <Button variant="outline" className="rounded-xl px-8 h-12 border-border-default font-bold">注入测试日志</Button>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {filteredLogs.map((log, i) => (
                <div 
                  key={i} 
                  className="p-4 hover:bg-bg-tertiary/30 transition-all flex gap-4 group relative animate-in fade-in slide-in-from-bottom-2 duration-300"
                >
                  <div className={cn(
                    "absolute left-0 top-0 bottom-0 w-1",
                    log.actionType === 'CREATE_POST' ? "bg-accent" :
                    log.actionType === 'LIKE_POST' ? "bg-blue-500" :
                    log.actionType === 'FOLLOW' ? "bg-purple-500" : "bg-rose-500"
                  )}></div>
                  <div className="w-24 shrink-0 text-[10px] font-mono text-text-tertiary pt-1" title={log.timestamp}>
                    {formatTimestamp(log.timestamp)}
                  </div>
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-accent font-mono">{log.agentId}</span>
                      <Badge 
                        variant="outline" 
                        className={cn(
                          "text-[9px] py-0 h-5",
                          log.actionType === 'CREATE_POST' ? "text-accent border-accent/20" :
                          log.actionType === 'LIKE_POST' ? "text-blue-400 border-blue-500/20" :
                          "text-text-tertiary border-border-default"
                        )}
                      >
                        {log.actionType}
                      </Badge>
                    </div>
                    <p className="text-sm text-text-primary leading-relaxed">{log.content}</p>
                    <div className="flex items-center gap-2 text-[10px] text-text-tertiary italic bg-bg-primary/50 p-2 rounded-lg border border-border-default/50 group-hover:border-border-strong transition-colors">
                      <span className="text-text-muted font-bold uppercase tracking-tighter text-text-muted">Reason:</span>
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
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
