import { useState } from 'react';
import { useSimulationStore } from '@/lib/store';
import { simulationApi } from '@/lib/api';
import { Card, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Slider, Badge } from '@/components/ui';
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
  Zap,
  MessageSquare,
  CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';
import { useLocation, useNavigate } from 'react-router-dom';
import { ScrollArea } from '@/components/ui';

export default function Control() {
  const { status, setRunning, logs, clearLogs } = useSimulationStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [platform, setPlatform] = useState(location.state?.platform || 'REDDIT');
  const [recsys, setRecsys] = useState('HOT');
  const [agentCount, setAgentCount] = useState([location.state?.agentCount || 1000]);
  const [speed, setSpeed] = useState([10]);
  const [topic, setTopic] = useState(location.state?.topic || 'POLITICS');
  const [region, setRegion] = useState(location.state?.region || 'THAILAND');

  const handleStart = async () => {
    try {
      clearLogs();
      await simulationApi.updateConfig({
        platform,
        recsys,
        agentCount: agentCount[0],
        speed: speed[0],
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
      await simulationApi.step();
      toast.info("执行单步模拟");
    } catch (error) {
      toast.error("步进执行失败");
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
            <Settings2 className="w-10 h-10 text-emerald-500" />
            控制中心
          </h1>
          <p className="text-zinc-500 mt-1">配置模拟参数并控制引擎执行</p>
        </div>
        <div className={cn(
          "px-6 py-3 rounded-2xl border flex items-center gap-3 transition-all duration-500",
          status.running 
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-500 shadow-[0_0_20px_rgba(16,185,129,0.1)]" 
            : "bg-zinc-900 border-zinc-800 text-zinc-500"
        )}>
          <div className={cn("w-3 h-3 rounded-full", status.running ? "bg-emerald-500 animate-pulse" : "bg-zinc-600")}></div>
          <span className="text-sm font-bold uppercase tracking-widest font-mono">
            {status.running ? 'System Running' : 'Ready to Initialize'}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration */}
        <Card className="bg-zinc-900 border-zinc-800 p-8 space-y-8">
          <div className="flex justify-between items-center border-b border-zinc-800 pb-4">
            <h2 className="text-xl font-bold">模拟参数配置</h2>
            <Badge variant="outline">v1.1 Config</Badge>
          </div>
          
          <div className="space-y-8">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">平台类型</label>
                <Select value={platform} onValueChange={setPlatform}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800 h-12 rounded-xl">
                    <SelectValue placeholder="选择平台" />
                    <span className="text-zinc-400">{platform}</span>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="REDDIT">Reddit (社区驱动)</SelectItem>
                    <SelectItem value="X">X / Twitter (流驱动)</SelectItem>
                    <SelectItem value="FACEBOOK">Facebook (关系驱动)</SelectItem>
                    <SelectItem value="TIKTOK">TikTok (算法驱动)</SelectItem>
                    <SelectItem value="INSTAGRAM">Instagram (视觉驱动)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-zinc-600 italic">不同平台影响 Agent 的初始拓扑结构</p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">推荐算法</label>
                <Select value={recsys} onValueChange={setRecsys}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800 h-12 rounded-xl">
                    <SelectValue placeholder="选择算法" />
                    <span className="text-zinc-400">{recsys}</span>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="HOT">Hot-score (Reddit/Facebook)</SelectItem>
                    <SelectItem value="TWHIN">TwHIN-BERT (X)</SelectItem>
                    <SelectItem value="FORYOU">For You (TikTok)</SelectItem>
                    <SelectItem value="EDGERANK">EdgeRank (Facebook/Instagram)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-[10px] text-zinc-600 italic">影响信息传播路径与从众概率</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">Topic 标签</label>
                <Select value={topic} onValueChange={setTopic}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800 h-12 rounded-xl">
                    <SelectValue placeholder="选择Topic" />
                    <span className="text-zinc-400">{topic}</span>
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
                <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">国际地区</label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger className="bg-zinc-950 border-zinc-800 h-12 rounded-xl">
                    <SelectValue placeholder="选择地区" />
                    <span className="text-zinc-400">{region}</span>
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
                <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">初始 Agent 数量</label>
                <div className="text-right">
                  <span className="text-3xl font-bold text-emerald-500 font-mono tracking-tighter">{agentCount[0].toLocaleString()}</span>
                  <p className="text-[10px] text-zinc-600 font-bold uppercase">Agents</p>
                </div>
              </div>
              <Slider 
                value={agentCount} 
                onValueChange={setAgentCount} 
                min={100} 
                max={100000} 
                step={100}
                className="py-4"
              />
              <div className="flex justify-between text-[10px] text-zinc-700 font-bold">
                <span>100</span>
                <span>1,000,000 (MAX)</span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-end">
                <label className="text-xs font-bold uppercase tracking-wider text-zinc-500">时间加速倍数</label>
                <div className="text-right">
                  <span className="text-3xl font-bold text-emerald-500 font-mono tracking-tighter">{speed[0]}x</span>
                  <p className="text-[10px] text-zinc-600 font-bold uppercase">Speed</p>
                </div>
              </div>
              <Slider 
                value={speed} 
                onValueChange={setSpeed} 
                min={1} 
                max={100} 
                step={1}
                className="py-4"
              />
              <div className="p-3 bg-zinc-950 rounded-xl border border-zinc-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="w-3 h-3 text-yellow-500" />
                  <span className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">预计单步耗时</span>
                </div>
                <span className="text-xs font-mono text-emerald-500 font-bold">≈ {(12 / speed[0]).toFixed(1)} 秒</span>
              </div>
            </div>
          </div>

          <div className="pt-4 space-y-4">
            <div className="flex gap-3">
              <Button onClick={() => applyPreset(1000, 10, 'REDDIT', 'HOT')} variant="outline" className="flex-1 h-10 text-[10px] font-bold uppercase tracking-widest border-zinc-800">教学模式</Button>
              <Button onClick={() => applyPreset(10000, 25, 'X', 'TWHIN')} variant="outline" className="flex-1 h-10 text-[10px] font-bold uppercase tracking-widest border-zinc-800">研究模式</Button>
              <Button onClick={() => applyPreset(100000, 50, 'TIKTOK', 'FORYOU')} variant="outline" className="flex-1 h-10 text-[10px] font-bold uppercase tracking-widest border-zinc-800 text-rose-400 border-rose-500/20">压力测试</Button>
            </div>
            <Button 
              variant="outline" 
              className="w-full h-12 rounded-xl border-zinc-800 hover:bg-zinc-800 text-zinc-400 font-bold gap-2 text-xs uppercase tracking-widest"
              onClick={() => toast.success("配置已保存为模板")}
            >
              <Save className="w-4 h-4" />
              保存当前配置为模板
            </Button>
          </div>

          {/* 实时日志预览框（新增） */}
          <Card className="mt-8 bg-zinc-900 border-zinc-800">
            <div className="p-4 border-b border-zinc-800">
              <h3 className="text-sm font-bold flex items-center gap-2 text-zinc-200">
                <MessageSquare className="w-4 h-4 text-emerald-500" /> 
                启动后实时日志预览
              </h3>
            </div>
            <div className="p-4">
              <ScrollArea className="h-48 bg-zinc-950 rounded-xl p-4 font-mono text-xs border border-zinc-800">
                {logs.length === 0 ? (
                  <div className="text-zinc-600 italic text-center py-12 flex flex-col items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-zinc-900 flex items-center justify-center">
                      <MessageSquare className="w-4 h-4 text-zinc-700" />
                    </div>
                    启动模拟后日志将实时显示在这里...
                  </div>
                ) : (
                  logs.slice(0, 10).map((log, i) => (
                    <div key={i} className="py-1.5 border-b border-zinc-800/50 last:border-0 flex items-start gap-3">
                      <span className="text-emerald-500/70 whitespace-nowrap">[{log.timestamp}]</span> 
                      <span className="text-zinc-400 font-bold w-12 truncate">{log.agentId}</span> 
                      <span className="text-rose-400/80 font-bold w-24">{log.actionType}</span>
                      <span className="text-zinc-300 flex-1 truncate">"{log.content}"</span>
                    </div>
                  ))
                )}
              </ScrollArea>
            </div>
          </Card>
        </Card>

        {/* Operations */}
        <Card className="bg-zinc-900 border-zinc-800 p-8 flex flex-col">
          <h2 className="text-xl font-bold border-b border-zinc-800 pb-4 mb-8">模拟执行控制</h2>
          
          <div className="grid grid-cols-2 gap-6 flex-1">
            <Button 
              onClick={handleStart}
              disabled={status.running}
              className={cn(
                "h-40 rounded-3xl flex flex-col gap-4 text-xl font-black shadow-2xl transition-all active:scale-95",
                status.running 
                  ? "bg-zinc-800 text-zinc-500 border border-zinc-700 shadow-none" 
                  : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-500/20"
              )}
            >
              <div className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center",
                status.running ? "bg-zinc-700" : "bg-white/20"
              )}>
                {status.running ? <CheckCircle2 className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current" />}
              </div>
              {status.running ? '模拟运行中' : '启动模拟'}
            </Button>
            
            <Button 
              onClick={() => setRunning(false)}
              disabled={!status.running}
              variant="outline"
              className="h-40 rounded-3xl border-zinc-800 hover:bg-zinc-800 flex flex-col gap-4 text-xl font-black disabled:opacity-30 transition-all active:scale-95"
            >
              <div className="w-12 h-12 bg-zinc-800 rounded-full flex items-center justify-center">
                <Pause className="w-6 h-6 fill-current" />
              </div>
              暂停模拟
            </Button>

            <Button 
              onClick={handleStep}
              disabled={!status.running}
              variant="secondary"
              className="h-24 rounded-2xl bg-zinc-800 hover:bg-zinc-700 flex items-center justify-center gap-4 text-lg font-bold col-span-2 group"
            >
              <StepForward className="w-6 h-6 group-active:translate-x-1 transition-transform" />
              单步执行 (Step)
              <span className="text-[10px] bg-zinc-900 px-2 py-1 rounded border border-zinc-700 text-zinc-500 ml-2">Ctrl + Enter</span>
            </Button>

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
              className="h-20 rounded-2xl border-zinc-800 hover:bg-zinc-800 flex items-center gap-3 font-bold text-base"
            >
              <RotateCcw className="w-5 h-5" />
              重置环境
            </Button>
          </div>

          <div className="mt-8 p-6 rounded-2xl bg-zinc-950 border border-zinc-800 relative overflow-hidden group">
            <div className="absolute inset-0 bg-emerald-500/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <div className="flex items-center justify-between relative z-10">
              <div className="flex items-center gap-3">
                <div className={cn("w-2 h-2 rounded-full", status.running ? "bg-emerald-500 animate-pulse" : "bg-zinc-600")}></div>
                <span className="text-xs font-mono font-bold text-zinc-400 uppercase tracking-widest">
                  {status.running ? 'Engine Active' : 'Engine Standby'}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-[10px] text-zinc-600 font-mono">STEP: {status.currentStep}</span>
                {status.running && (
                  <Button 
                    variant="ghost" 
                    className="h-6 px-2 text-[10px] text-emerald-500 hover:text-emerald-400 hover:bg-emerald-500/10 gap-1"
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
