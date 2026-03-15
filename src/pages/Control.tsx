import { useState, useEffect } from 'react';
import { useSimulationStore } from '@/lib/store';
import { simulationApi } from '@/lib/api';
import { Card, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Slider, Badge, Progress } from '@/components/ui';
import { cn } from '@/lib/utils';
import {
  Play,
  Pause,
  StepForward,
  Square,
  RotateCcw,
  Settings2,
  ArrowRight,
  Save,
  MessageSquare
} from 'lucide-react';
import { toast } from 'sonner';
import { useLocation, useNavigate } from 'react-router-dom';
import { ScrollArea } from '@/components/ui';
import { io } from 'socket.io-client';

export default function Control() {
  const { status, setRunning, logs, clearLogs, setStatus } = useSimulationStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [platform, setPlatform] = useState(location.state?.platform || 'REDDIT');
  const [recsys, setRecsys] = useState('HOT');
  const [agentCount, setAgentCount] = useState([location.state?.agentCount || 10]); // 默认值为10
  const [topic, setTopic] = useState(location.state?.topic || 'POLITICS');
  const [region, setRegion] = useState(location.state?.region || 'THAILAND');
  const [stepProgress, setStepProgress] = useState({ current: 0, total: 0, percentage: 0 });
  const [isStepping, setIsStepping] = useState(false);

  // WebSocket 连接，监听进度
  useEffect(() => {
    const socket = io('http://localhost:3000');

    socket.on('step_progress', (progress) => {
      setStepProgress(progress);
    });

    socket.on('step_complete', () => {
      setIsStepping(false);
      setStepProgress({ current: 0, total: 0, percentage: 0 });
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // 同步后端状态（修复刷新后状态丢失问题）
  useEffect(() => {
    const syncStatus = async () => {
      try {
        const res = await simulationApi.getStatus();
        if (res.data) {
          setStatus(res.data);
        }
      } catch (error) {
        console.error('Failed to sync status:', error);
      }
    };

    syncStatus();
    const interval = setInterval(syncStatus, 2000); // 每2秒同步
    return () => clearInterval(interval);
  }, [setStatus]);

  const handleStart = async () => {
    try {
      clearLogs();
      await simulationApi.updateConfig({
        platform,
        recsys,
        agentCount: agentCount[0],
        topics: [topic],
        regions: [region],
      });
      setRunning(true);
      toast.success("模拟已启动！", {
        description: `平台: ${platform} | 算法: ${recsys} | 地区: ${region}`,
        action: {
          label: "查看监控",
          onClick: () => navigate('/agents')
        },
        duration: 5000,
      });
    } catch (error) {
      toast.error("启动失败，请检查引擎连接");
    }
  };

  const handleStep = async () => {
    try {
      setIsStepping(true);
      setStepProgress({ current: 0, total: agentCount[0], percentage: 0 });
      await simulationApi.step();
      toast.info("执行单步模拟完成");
      setIsStepping(false);
    } catch (error) {
      toast.error("步进执行失败");
      setIsStepping(false);
    }
  };

  const handleReset = async () => {
    if (confirm('确定要重置环境吗？所有当前进度将丢失。')) {
      await simulationApi.reset();
      toast.warning("环境已重置");
    }
  };

  const applyPreset = (count: number, spd: number, p: string, r: string) => {
    setAgentCount([count]);
    setSpeed([spd]);
    setPlatform(p);
    setRecsys(r);
    toast.info(`已加载预设: ${p} ${count} Agents`);
  };

  return (
    <div className="px-6 lg:px-12 xl:px-16 py-12">
      <div className="max-w-7xl mx-auto space-y-8">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl tracking-tight flex items-center gap-3">
            <Settings2 className="w-10 h-10 text-accent" />
            控制中心
          </h1>
          <p className="text-text-tertiary mt-1">参数配置与控制</p>
        </div>
        <div className={cn(
          "px-6 py-3 rounded-full border flex items-center gap-3 transition-all duration-500",
          status.running && !status.paused
            ? "bg-green-50 border-green-200 text-green-600 dark:bg-green-950 dark:border-green-800 dark:text-green-400"
            : status.paused
            ? "bg-bg-tertiary border-border-default text-text-secondary"
            : "bg-bg-tertiary border-border-default text-text-tertiary"
        )}>
          <div className={cn(
            "w-3 h-3 rounded-full",
            status.running && !status.paused ? "bg-green-500 animate-pulse shadow-lg shadow-green-500/50" :
            status.paused ? "bg-text-secondary" : "bg-text-muted"
          )}></div>
          <span className="text-sm tracking-widest">
            {status.running && !status.paused ? '运行中' : status.paused ? '已暂停' : '待启动'}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration */}
        <Card className="bg-bg-secondary border-border-default p-8 space-y-8">
          <div className="flex justify-between items-center border-b border-border-default pb-4">
            <h2 className="text-xl">参数配置</h2>
          </div>
          
          <div className="space-y-8">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">平台</label>
                <Select value={platform} onValueChange={setPlatform}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择平台" value={platform} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="REDDIT">Reddit</SelectItem>
                    <SelectItem value="X">X</SelectItem>
                    <SelectItem value="FACEBOOK">Facebook</SelectItem>
                    <SelectItem value="TIKTOK">TikTok</SelectItem>
                    <SelectItem value="INSTAGRAM">Instagram</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">算法</label>
                <Select value={recsys} onValueChange={setRecsys}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择算法" value={recsys} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOT">Hot-score</SelectItem>
                    <SelectItem value="TWHIN">TwHIN-BERT</SelectItem>
                    <SelectItem value="FORYOU">For You</SelectItem>
                    <SelectItem value="EDGERANK">EdgeRank</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">话题</label>
                <Select value={topic} onValueChange={setTopic}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择话题" value={topic} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="POLITICS">Politics</SelectItem>
                    <SelectItem value="AI">AI & Tech</SelectItem>
                    <SelectItem value="ENTERTAINMENT">Entertainment</SelectItem>
                    <SelectItem value="HEALTH">Health</SelectItem>
                    <SelectItem value="TRAVEL">Travel</SelectItem>
                    <SelectItem value="FOOD">Food</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">地区</label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择地区" value={region} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="THAILAND">Thailand</SelectItem>
                    <SelectItem value="CAMBODIA">Cambodia</SelectItem>
                    <SelectItem value="INDONESIA">Indonesia</SelectItem>
                    <SelectItem value="VIETNAM">Vietnam</SelectItem>
                    <SelectItem value="MALAYSIA">Malaysia</SelectItem>
                    <SelectItem value="PHILIPPINES">Philippines</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-end">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">Agent 数量</label>
                <div className="text-right">
                  <span className="text-3xl text-accent tracking-tighter">{agentCount[0].toLocaleString()}</span>
                  <p className="text-xs text-text-muted uppercase">Agents</p>
                </div>
              </div>
              <Slider
                value={agentCount}
                onValueChange={setAgentCount}
                min={10}
                max={100000}
                step={10}
                className="py-4"
              />
              <div className="flex justify-between text-xs text-text-muted">
                <span>10</span>
                <span>100,000</span>
              </div>
            </div>
          </div>

          {/* 实时日志预览框（新增） */}
          <Card className="mt-8 bg-bg-secondary border-border-default">
            <div className="p-4 border-b border-border-default">
              <h3 className="text-sm flex items-center gap-2 text-text-primary">
                <MessageSquare className="w-4 h-4 text-accent" />
                日志预览
              </h3>
            </div>
            <div className="p-4">
              <ScrollArea className="h-48 bg-bg-primary rounded-xl p-4 text-xs border border-border-default">
                {logs.length === 0 ? (
                  <div className="text-text-muted italic text-center py-12 flex flex-col items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-bg-secondary flex items-center justify-center">
                      <MessageSquare className="w-4 h-4 text-text-muted" />
                    </div>
                    启动后显示日志
                  </div>
                ) : (
                  logs.slice(0, 10).map((log, i) => (
                    <div key={i} className="py-1.5 border-b border-border-default/50 last:border-0 flex items-start gap-3">
                      <span className="text-accent/70 whitespace-nowrap">[{log.timestamp}]</span> 
                      <span className="text-text-secondary w-12 truncate">{log.agentId}</span> 
                      <span className="text-rose-400/80 w-24">{log.actionType}</span>
                      <span className="text-text-primary flex-1 truncate">"{log.content}"</span>
                    </div>
                  ))
                )}
              </ScrollArea>
            </div>
          </Card>
        </Card>

        {/* Operations */}
        <Card className={cn(
          "bg-bg-secondary border-border-default p-8 flex flex-col relative overflow-hidden transition-all duration-500",
          status.running && !status.paused && "shadow-lg shadow-green-500/20"
        )}>
          {/* 绿光效果 */}
          {status.running && !status.paused && (
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute inset-0 bg-gradient-to-br from-green-500/10 via-transparent to-transparent"></div>
              <div className="absolute -top-24 -right-24 w-48 h-48 bg-green-500/20 rounded-full blur-3xl animate-pulse"></div>
              <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-green-500/10 rounded-full blur-3xl animate-pulse delay-1000"></div>
            </div>
          )}

          <h2 className="text-xl border-b border-border-default pb-4 mb-8 relative z-10">执行控制</h2>

          <div className="flex-1 relative z-10 flex flex-col justify-between gap-6">
            {/* 主控制区 */}
            <Button
              onClick={async () => {
                if (status.running && !status.paused) {
                  try {
                    await simulationApi.pause();
                    toast.success("模拟已暂停");
                  } catch (error) {
                    toast.error("暂停失败");
                  }
                } else if (status.paused) {
                  try {
                    await simulationApi.resume();
                    toast.success("模拟已恢复");
                  } catch (error) {
                    toast.error("恢复失败");
                  }
                } else {
                  handleStart();
                }
              }}
              className={cn(
                "h-14 rounded-xl flex-row gap-3 text-base transition-all active:scale-98 px-6",
                status.running && !status.paused
                  ? "bg-gradient-to-br from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white shadow-xl shadow-green-500/30"
                  : "bg-gradient-to-br from-accent to-accent-hover hover:from-accent-hover hover:to-accent text-white shadow-xl shadow-accent/30"
              )}
            >
              <div className={cn(
                "w-10 h-10 rounded-full flex items-center justify-center transition-all shrink-0",
                status.running && !status.paused
                  ? "bg-white/20 animate-pulse"
                  : "bg-white/10"
              )}>
                {status.running && !status.paused
                  ? <Pause className="w-5 h-5 fill-current" />
                  : <Play className="w-5 h-5 fill-current" />
                }
              </div>
              <span className="font-medium">{status.running && !status.paused ? '暂停模拟' : status.paused ? '恢复模拟' : '启动模拟'}</span>
            </Button>

            {/* 次要控制区 - 2x1 网格 */}
            <div className="grid grid-cols-2 gap-6">
              <Button
                onClick={handleStep}
                disabled={(!status.running && !status.paused) || isStepping}
                variant="secondary"
                className="h-14 rounded-xl flex-row items-center justify-center gap-2 text-sm"
              >
                <StepForward className="w-4 h-4" />
                <span>{isStepping ? '执行中...' : '单步执行'}</span>
              </Button>

              <Button
                onClick={handleReset}
                variant="outline"
                className="h-14 rounded-xl flex-row items-center justify-center gap-2 text-sm"
              >
                <RotateCcw className="w-4 h-4" />
                <span>重置环境</span>
              </Button>
            </div>

            {/* 进度条 - 动态插入 */}
            {isStepping && stepProgress.total > 0 && (
              <div className="mb-3 p-3 rounded-xl bg-bg-primary/60 border border-border-default/40 backdrop-blur-sm">
                <div className="flex justify-between text-xs text-text-tertiary mb-2">
                  <span>执行进度</span>
                  <span className="font-medium">{stepProgress.current} / {stepProgress.total}</span>
                </div>
                <Progress value={stepProgress.percentage} className="h-1.5 bg-bg-tertiary" />
              </div>
            )}

            {/* 危险操作区 - 紧凑 */}
            <Button
              variant="destructive"
              className="h-14 rounded-xl flex-row items-center justify-center gap-2 text-sm"
              onClick={() => {
                if (confirm('确定要终止模拟并导出数据吗？')) {
                  toast.success("模拟已终止，数据导出中...");
                }
              }}
            >
              <Square className="w-4 h-4" />
              终止模拟
            </Button>
          </div>

          <div className="mt-8 p-6 rounded-xl bg-bg-primary border border-border-default relative overflow-hidden group">
            <div className="absolute inset-0 bg-green-500/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  status.running ? "bg-green-500 animate-pulse shadow-lg shadow-green-500/50" : "bg-text-muted"
                )}></div>
                <span className={cn(
                  "text-xs tracking-widest",
                  status.running ? "text-green-600 dark:text-green-400" : "text-text-secondary"
                )}>
                  {status.paused ? '已暂停' : status.running ? '运行中' : '待机'}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-xs text-text-muted">{status.currentStep}</span>
                {(status.running || status.paused) && (
                  <Button
                    variant="ghost"
                    className="h-6 px-2 text-xs text-accent hover:text-accent hover:bg-accent-subtle gap-1"
                    onClick={() => navigate('/agents')}
                  >
                    监控中 <ArrowRight className="w-3 h-3" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Card>
      </div>
      </div>
    </div>
  );
}
