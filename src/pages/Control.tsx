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
  MessageSquare,
  CheckCircle2
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
  const [agentCount, setAgentCount] = useState([location.state?.agentCount || 100]); // 修改默认值为100
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
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <Settings2 className="w-10 h-10 text-accent" />
            控制中心
          </h1>
          <p className="text-text-tertiary mt-1">配置模拟参数并控制引擎执行</p>
        </div>
        <div className={cn(
          "px-6 py-3 rounded-2xl border flex items-center gap-3 transition-all duration-500",
          status.running && !status.paused
            ? "bg-accent-subtle border-accent/30 text-accent shadow-[0_0_20px_rgba(16,185,129,0.1)]"
            : status.paused
            ? "bg-amber-500/10 border-amber-500/30 text-amber-500 shadow-[0_0_20px_rgba(245,158,11,0.1)]"
            : "bg-bg-secondary border-border-default text-text-tertiary"
        )}>
          <div className={cn(
            "w-3 h-3 rounded-full",
            status.running && !status.paused ? "bg-accent animate-pulse" :
            status.paused ? "bg-amber-500" : "bg-text-muted"
          )}></div>
          <span className="text-sm font-bold uppercase tracking-widest font-mono">
            {status.running && !status.paused ? 'System Running' : status.paused ? 'System Paused' : 'Ready to Initialize'}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration */}
        <Card className="bg-bg-secondary border-border-default p-8 space-y-8">
          <div className="flex justify-between items-center border-b border-border-default pb-4">
            <h2 className="text-xl font-bold">模拟参数配置</h2>
            <Badge variant="outline">v1.1 Config</Badge>
          </div>
          
          <div className="space-y-8">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">平台类型</label>
                <Select value={platform} onValueChange={setPlatform}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择平台" value={platform} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="REDDIT">Reddit (社区驱动)</SelectItem>
                    <SelectItem value="X">X / Twitter (流驱动)</SelectItem>
                    <SelectItem value="FACEBOOK">Facebook (关系驱动)</SelectItem>
                    <SelectItem value="TIKTOK">TikTok (算法驱动)</SelectItem>
                    <SelectItem value="INSTAGRAM">Instagram (视觉驱动)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-text-muted italic">不同平台影响 Agent 的初始拓扑结构</p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">推荐算法</label>
                <Select value={recsys} onValueChange={setRecsys}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择算法" value={recsys} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOT">Hot-score (Reddit/Facebook)</SelectItem>
                    <SelectItem value="TWHIN">TwHIN-BERT (X)</SelectItem>
                    <SelectItem value="FORYOU">For You (TikTok)</SelectItem>
                    <SelectItem value="EDGERANK">EdgeRank (Facebook/Instagram)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-text-muted italic">影响信息传播路径与从众概率</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">Topic 标签</label>
                <Select value={topic} onValueChange={setTopic}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择Topic" value={topic} />
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
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">国际地区</label>
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
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">初始 Agent 数量</label>
                <div className="text-right">
                  <span className="text-3xl font-bold text-accent font-mono tracking-tighter">{agentCount[0].toLocaleString()}</span>
                  <p className="text-[10px] text-text-muted font-bold uppercase">Agents</p>
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
              <div className="flex justify-between text-[10px] text-text-muted font-bold">
                <span>10</span>
                <span>100,000 (MAX)</span>
              </div>
            </div>
          </div>

          <div className="pt-4 space-y-4">
            <div className="flex gap-3">
              <Button onClick={() => applyPreset(1000, 10, 'REDDIT', 'HOT')} variant="outline" className="flex-1 h-10 text-[10px] font-bold uppercase tracking-widest border-border-default">教学模式</Button>
              <Button onClick={() => applyPreset(10000, 25, 'X', 'TWHIN')} variant="outline" className="flex-1 h-10 text-[10px] font-bold uppercase tracking-widest border-border-default">研究模式</Button>
              <Button onClick={() => applyPreset(100000, 50, 'TIKTOK', 'FORYOU')} variant="outline" className="flex-1 h-10 text-[10px] font-bold uppercase tracking-widest border-border-default text-rose-400 border-rose-500/20">压力测试</Button>
            </div>
            <Button 
              variant="outline" 
              className="w-full h-12 rounded-xl border-border-default hover:bg-bg-tertiary text-text-secondary font-bold gap-2 text-xs uppercase tracking-widest"
              onClick={() => toast.success("配置已保存为模板")}
            >
              <Save className="w-4 h-4" />
              保存当前配置为模板
            </Button>
          </div>

          {/* 实时日志预览框（新增） */}
          <Card className="mt-8 bg-bg-secondary border-border-default">
            <div className="p-4 border-b border-border-default">
              <h3 className="text-sm font-bold flex items-center gap-2 text-text-primary">
                <MessageSquare className="w-4 h-4 text-accent" /> 
                启动后实时日志预览
              </h3>
            </div>
            <div className="p-4">
              <ScrollArea className="h-48 bg-bg-primary rounded-xl p-4 font-mono text-xs border border-border-default">
                {logs.length === 0 ? (
                  <div className="text-text-muted italic text-center py-12 flex flex-col items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-bg-secondary flex items-center justify-center">
                      <MessageSquare className="w-4 h-4 text-text-muted" />
                    </div>
                    启动模拟后日志将实时显示在这里...
                  </div>
                ) : (
                  logs.slice(0, 10).map((log, i) => (
                    <div key={i} className="py-1.5 border-b border-border-default/50 last:border-0 flex items-start gap-3">
                      <span className="text-accent/70 whitespace-nowrap">[{log.timestamp}]</span> 
                      <span className="text-text-secondary font-bold w-12 truncate">{log.agentId}</span> 
                      <span className="text-rose-400/80 font-bold w-24">{log.actionType}</span>
                      <span className="text-text-primary flex-1 truncate">"{log.content}"</span>
                    </div>
                  ))
                )}
              </ScrollArea>
            </div>
          </Card>
        </Card>

        {/* Operations */}
        <Card className="bg-bg-secondary border-border-default p-8 flex flex-col">
          <h2 className="text-xl font-bold border-b border-border-default pb-4 mb-8">模拟执行控制</h2>
          
          <div className="grid grid-cols-2 gap-6 flex-1">
            <Button
              onClick={async () => {
                if (status.paused) {
                  // 恢复模拟
                  try {
                    await simulationApi.resume();
                    toast.success("模拟已恢复");
                  } catch (error) {
                    toast.error("恢复失败");
                  }
                } else {
                  // 启动新模拟
                  handleStart();
                }
              }}
              disabled={status.running && !status.paused}
              className={cn(
                "h-40 rounded-3xl flex flex-col gap-4 text-xl font-black shadow-2xl transition-all active:scale-95",
                status.running && !status.paused
                  ? "bg-bg-tertiary text-text-tertiary border border-border-strong shadow-none"
                  : status.paused
                  ? "bg-amber-600 hover:bg-amber-700 shadow-amber-500/20"
                  : "bg-accent hover:bg-accent-hover shadow-accent-glow"
              )}
            >
              <div className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center",
                status.running && !status.paused ? "bg-bg-elevated" : "bg-bg-primary/20"
              )}>
                {status.running && !status.paused ? <CheckCircle2 className="w-6 h-6 fill-current" /> :
                 status.paused ? <Play className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
              </div>
              {status.running && !status.paused ? '模拟运行中' : status.paused ? '恢复模拟' : '启动模拟'}
            </Button>
            
            <Button
              onClick={async () => {
                try {
                  await simulationApi.pause();
                  toast.success("模拟已暂停");
                } catch (error) {
                  toast.error("暂停失败");
                }
              }}
              disabled={!status.running || status.paused}
              variant="outline"
              className="h-40 rounded-3xl border-border-default hover:bg-bg-tertiary flex flex-col gap-4 text-xl font-black disabled:opacity-30 transition-all active:scale-95"
            >
              <div className="w-12 h-12 bg-bg-tertiary rounded-full flex items-center justify-center">
                <Pause className="w-6 h-6 fill-current" />
              </div>
              暂停模拟
            </Button>

            <Button
              onClick={handleStep}
              disabled={(!status.running && !status.paused) || isStepping}
              variant="secondary"
              className="h-24 rounded-2xl bg-bg-tertiary hover:bg-bg-elevated flex items-center justify-center gap-4 text-lg font-bold col-span-2 group"
            >
              <StepForward className="w-6 h-6 group-active:translate-x-1 transition-transform" />
              {isStepping ? '执行中...' : '单步执行 (Step)'}
              <span className="text-[10px] bg-bg-secondary px-2 py-1 rounded border border-border-strong text-text-tertiary ml-2">Ctrl + Enter</span>
            </Button>

            {/* 进度条 */}
            {isStepping && stepProgress.total > 0 && (
              <div className="col-span-2 space-y-2">
                <div className="flex justify-between text-xs text-text-tertiary">
                  <span>Agent 进度</span>
                  <span>{stepProgress.current} / {stepProgress.total} ({stepProgress.percentage}%)</span>
                </div>
                <Progress value={stepProgress.percentage} className="h-2 bg-bg-tertiary" />
              </div>
            )}

            <Button 
              variant="destructive"
              className="h-20 rounded-2xl flex items-center gap-3 font-bold text-base"
              onClick={() => {
                if (confirm('确定要终止模拟并导出数据吗？')) {
                  toast.success("模拟已终止，数据导出中...");
                }
              }}
            >
              <Square className="w-5 h-5 fill-current" />
              终止并导出
            </Button>

            <Button 
              onClick={handleReset}
              variant="outline"
              className="h-20 rounded-2xl border-border-default hover:bg-bg-tertiary flex items-center gap-3 font-bold text-base"
            >
              <RotateCcw className="w-5 h-5" />
              重置环境
            </Button>
          </div>

          <div className="mt-8 p-6 rounded-2xl bg-bg-primary border border-border-default relative overflow-hidden group">
            <div className="absolute inset-0 bg-accent/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center gap-3">
                <div className={cn("w-2 h-2 rounded-full", status.running ? "bg-accent animate-pulse" : "bg-text-muted")}></div>
                <span className="text-xs font-mono font-bold text-text-secondary uppercase tracking-widest">
                  {status.paused ? 'Engine Paused' : status.running ? 'Engine Active' : 'Engine Standby'}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-[10px] text-text-muted font-mono">STEP: {status.currentStep}</span>
                {(status.running || status.paused) && (
                  <Button
                    variant="ghost"
                    className="h-6 px-2 text-[10px] text-accent hover:text-accent hover:bg-accent-subtle gap-1"
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
  );
}
