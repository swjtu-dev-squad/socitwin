import { useEffect, useState, useMemo } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Button, Badge, Slider, Progress, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, ScrollArea } from '@/components/ui';
import { useNavigate } from 'react-router-dom';
import { simulationApi } from '@/lib/api';
import {
  Users,
  FileText,
  Activity,
  Zap,
  TrendingUp,
  Globe,
  Cpu,
  Eye,
  Play,
  Pause,
  StepForward,
  RotateCcw,
  Settings2,
  AlertCircle,
  ShieldAlert,
  Lightbulb,
  Share2,
  MousePointer2,
  Database,
  BookOpen,
  Users2,
  Wand2,
  UploadCloud,
  Layers,
  Info,
  ChevronRight,
  Search,
  Target,
  BarChart3,
  Network,
  ArrowUpRight,
  ArrowDownRight,
  PieChart as PieChartIcon
} from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
  ReferenceLine,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell
} from 'recharts';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'motion/react';
import { SituationalAwarenessChart } from '@/components/SituationalAwarenessChart';

export default function Overview() {
  const { status, history, setStatus, stepProgress, isStepping, setIsStepping } = useSimulationStore();
  const navigate = useNavigate();
  const [agentCount, setAgentCount] = useState([100]);
  const [subscriptionSource, setSubscriptionSource] = useState('REDDIT');
  const [topicBook, setTopicBook] = useState('TOPIC_01');
  const [userGroup, setUserGroup] = useState('GROUP_A');
  const [showAlgorithm, setShowAlgorithm] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await simulationApi.getStatus();
        setStatus(res.data);
      } catch (error) {
        console.error('Failed to fetch status:', error);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [setStatus]);
  
  // Conceptual simulated data for trend evolution
  const chartData: any[] = useMemo(() => {
    const steps = 60;
    return Array.from({ length: steps }, (_, i) => {
      // Phase 1: Incubation (0-20)
      // Phase 2: Rapid Growth (20-45)
      // Phase 3: Polarization/Saturation (45-60)
      
      let pol = 0.15;
      let prop = 0.05;
      let herd = 0.1;

      if (i < 20) {
        pol += Math.random() * 0.05;
        prop += (i / 20) * 0.1 + Math.random() * 0.05;
        herd += Math.random() * 0.05;
      } else if (i < 45) {
        pol += (i - 20) / 25 * 0.4 + Math.random() * 0.1;
        prop += 0.1 + (i - 20) / 25 * 0.6 + Math.random() * 0.1;
        herd += (i - 20) / 25 * 0.3 + Math.random() * 0.1;
      } else {
        pol = 0.65 + Math.sin(i / 2) * 0.05 + Math.random() * 0.05;
        prop = 0.85 - (i - 45) / 15 * 0.1 + Math.random() * 0.05;
        herd = 0.55 + (i - 45) / 15 * 0.2 + Math.random() * 0.05;
      }

      return {
        currentStep: i,
        polarization: Math.min(pol, 0.95),
        propagation: Math.min(prop, 0.98),
        herding: Math.min(herd, 0.92),
      };
    });
  }, []);

  const stats = [
    { label: '活跃 Agents', value: status.activeAgents.toLocaleString(), icon: Users, color: 'text-accent', path: '/agents' },
    { label: '当前步数', value: status.currentStep.toLocaleString(), icon: Zap, color: 'text-amber-400', path: '/overview' },
  ];

  // Industrial Border Style
  const industrialCardClass = "bg-bg-secondary border-2 border-accent/30 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-2 before:h-2 before:border-t-2 before:border-l-2 before:border-accent after:absolute after:bottom-0 after:right-0 after:w-2 after:h-2 after:border-b-2 after:border-r-2 after:border-accent";

  // Cognitive Warning Logic (Mock)
  const threatLevel = useMemo(() => {
    const lastData = chartData[chartData.length - 1];
    const avg = (lastData.polarization + lastData.propagation + lastData.herding) / 3; 
    if (avg > 0.7) return { label: '高危', color: 'text-rose-500', bg: 'bg-rose-500/10', border: 'border-rose-500/20' };
    if (avg > 0.4) return { label: '中等', color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/20' };
    return { label: '安全', color: 'text-accent', bg: 'bg-accent/10', border: 'border-accent/20' };
  }, [chartData]);

  const handleSimulate = () => {
    setIsSimulating(true);
    setTimeout(() => {
      setIsSimulating(false);
      toast.success('策略模拟评估完成');
    }, 3000);
  };

  const opinionDistribution = [
    { name: '极左', value: 15, color: '#f43f5e' },
    { name: '中立', value: 55, color: '#71717a' },
    { name: '极右', value: 30, color: '#3b82f6' },
  ];

  const metrics = [
    { label: '群体极化率', value: `${(status.polarization * 100).toFixed(1)}%`, trend: '+2.4%', up: true, icon: Zap, color: 'text-rose-500' },
    { label: '信息传播速度', value: `${(status.velocity || 12.4).toFixed(1)} msg/s`, trend: '+12%', up: true, icon: TrendingUp, color: 'text-emerald-500' },
    { label: '从众效应指数', value: `${((status.herdHhi || 0.24) * 100).toFixed(1)}%`, trend: '-0.5%', up: false, icon: Users, color: 'text-blue-500' },
    { label: '活跃节点密度', value: '0.84', trend: '+0.02', up: true, icon: Activity, color: 'text-amber-500' },
  ];

  return (
    <div className="px-6 lg:px-12 py-10 space-y-8 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] min-h-screen">
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="flex-1">
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3 text-accent drop-shadow-[0_0_10px_rgba(0,242,255,0.3)]">
            <Eye className="w-10 h-10" />
            态势推演 <span className="text-xs font-mono opacity-50 border border-accent/30 px-2 py-0.5 rounded ml-2 tracking-[0.3em]">SOCITWIN_MONITOR_V2</span>
          </h1>
          <p className="text-text-tertiary mt-1 font-mono text-sm uppercase tracking-wider">Real-time simulation & cognitive trend analysis // Secure Environment</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-3 bg-bg-secondary/80 backdrop-blur-sm p-1.5 pl-4 rounded-lg border-2 border-accent/30">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
              <Database className="w-3 h-3" />
              订阅源
            </div>
            <Select 
              value={subscriptionSource} 
              onValueChange={(val) => {
                setSubscriptionSource(val);
                simulationApi.updateConfig({ platform: val });
              }}
            >
              <SelectTrigger className="h-8 text-xs border-none bg-transparent w-40 text-text-primary focus:ring-0">
                <SelectValue placeholder="选择订阅源" value={subscriptionSource} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="REDDIT">Reddit (Global)</SelectItem>
                <SelectItem value="TWITTER">Twitter (X)</SelectItem>
                <SelectItem value="TIKTOK">TikTok (Short-term)</SelectItem>
                <SelectItem value="XHS">Xiaohongshu (Quality)</SelectItem>
                <SelectItem value="PINTEREST">Pinterest (Visual)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-3">
            <AnimatePresence mode="wait">
              <motion.div
                key={status.running ? 'running' : 'stopped'}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className={cn(
                  "h-9 flex items-center gap-2 px-4 rounded-lg border-2 text-xs font-bold uppercase tracking-widest",
                  status.running && !status.paused ? "bg-accent/10 border-accent/50 text-accent shadow-[0_0_15px_rgba(0,242,255,0.2)]" :
                  status.paused ? "bg-amber-500/10 border-amber-500/50 text-amber-500" : "bg-bg-tertiary border-border-default text-text-tertiary"
                )}
              >
                <div className={cn("w-2 h-2 rounded-full",
                  status.running && !status.paused ? "bg-accent animate-pulse shadow-[0_0_8px_#00f2ff]" :
                  status.paused ? "bg-amber-500" : "bg-text-muted"
                )}></div>
                {status.running && !status.paused ? 'Active' : status.paused ? 'Paused' : 'Idle'}
              </motion.div>
            </AnimatePresence>

            <Button variant="outline" className="h-9 rounded-lg border-accent/30 gap-2 text-accent hover:bg-accent/10 text-xs font-bold uppercase tracking-widest">
              <Share2 className="w-4 h-4" />
              导出分析报告
            </Button>
          </div>
        </div>
      </header>

      {/* Top Row: Stats & Cognitive Warning */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4 grid grid-cols-1 sm:grid-cols-2 gap-6">
          {stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card 
                className={cn("p-6 hover:bg-accent/5 transition-all cursor-pointer group h-full", industrialCardClass)}
                onClick={() => navigate(stat.path)}
              >
                <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
                  <stat.icon className="w-16 h-16" />
                </div>
                <div className="flex items-center gap-3 mb-4">
                  <div className={cn("p-2 rounded-lg bg-bg-primary border border-accent/20", stat.color)}>
                    <stat.icon className="w-5 h-5" />
                  </div>
                  <span className="text-xs font-bold text-text-tertiary uppercase tracking-widest">{stat.label}</span>
                </div>
                <div className="flex items-baseline gap-2">
                  <h3 className="text-3xl font-bold tracking-tighter text-text-primary">{stat.value}</h3>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Cognitive Warning Section */}
        <Card className={cn("lg:col-span-8 p-6 flex flex-col md:flex-row gap-8 items-center", industrialCardClass)}>
          <div className="flex-1 space-y-4 w-full">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <ShieldAlert className="w-5 h-5 text-rose-500" />
                </div>
                <h2 className="text-lg font-bold uppercase tracking-tight">认知预警系统 // COGNITIVE_ALERT</h2>
              </div>
              <Badge className={cn("px-3 py-1 font-mono", threatLevel.bg, threatLevel.color, threatLevel.border)}>
                {threatLevel.label}风险
              </Badge>
            </div>
            
            <div className="p-4 rounded-lg bg-bg-primary/50 border border-accent/20">
              <p className="text-xs text-text-secondary leading-relaxed font-mono">
                [LOG] 态势评估完成: 系统处于 <span className={cn("font-bold", threatLevel.color)}>{threatLevel.label}</span> 预警状态。极化指数已触及临界点。
              </p>
              <div className="mt-4 grid grid-cols-3 gap-4">
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>极化指数</span>
                    <span className="text-rose-500">0.72</span>
                  </div>
                  <Progress value={72} className="h-1 bg-bg-tertiary" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>传播速率</span>
                    <span className="text-emerald-500">0.45</span>
                  </div>
                  <Progress value={45} className="h-1 bg-bg-tertiary" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>从众效应</span>
                    <span className="text-amber-500">0.58</span>
                  </div>
                  <Progress value={58} className="h-1 bg-bg-tertiary" />
                </div>
              </div>
            </div>
          </div>

          <div className="w-full md:w-64 space-y-3">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
              <AlertCircle className="w-3 h-3" />
              预警指标突出
            </div>
            <div className="grid grid-cols-1 gap-2">
              <div className="flex items-center justify-between p-2 rounded-lg bg-bg-primary border border-accent/20">
                <span className="text-[10px] font-bold text-text-tertiary uppercase">极化突变</span>
                <Badge className="bg-rose-500/10 text-rose-500 border-rose-500/20 text-[9px]">Critical</Badge>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-bg-primary border border-accent/20">
                <span className="text-[10px] font-bold text-text-tertiary uppercase">信息茧房</span>
                <Badge className="bg-amber-500/10 text-amber-500 border-amber-500/20 text-[9px]">Warning</Badge>
              </div>
              <div className="flex items-center justify-between p-2 rounded-lg bg-bg-primary border border-accent/20">
                <span className="text-[10px] font-bold text-text-tertiary uppercase">舆论倒灌</span>
                <Badge className="bg-blue-500/10 text-blue-500 border-blue-500/20 text-[9px]">Info</Badge>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Combined Chart Section (Situational Awareness) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between px-2">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-accent/10 border border-accent/20">
              <TrendingUp className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h2 className="text-lg font-bold uppercase tracking-tight">综合态势趋势演化 // SITUATIONAL_AWARENESS</h2>
              <p className="text-xs text-text-tertiary font-mono">MODEL: COGNITIVE_DYNAMICS_V4 // REAL-TIME SENSING</p>
            </div>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            className="h-8 rounded-lg gap-2 text-[10px] font-bold uppercase tracking-widest border-accent/30 text-accent hover:bg-accent/10"
            onClick={() => setShowAlgorithm(!showAlgorithm)}
          >
            <Info className="w-3.5 h-3.5" />
            分析算法说明
          </Button>
        </div>

        <AnimatePresence>
          {showAlgorithm && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="p-4 rounded-lg bg-bg-primary border border-accent/30 text-xs text-text-tertiary leading-relaxed grid grid-cols-1 md:grid-cols-3 gap-6 font-mono">
                <div className="space-y-2">
                  <h4 className="font-bold text-accent uppercase tracking-widest flex items-center gap-2">
                    <Target className="w-3 h-3" /> 极化计算模型
                  </h4>
                  <p>采用 Esteban-Ray 极化测度算法，量化认知极端化程度。</p>
                </div>
                <div className="space-y-2">
                  <h4 className="font-bold text-emerald-500 uppercase tracking-widest flex items-center gap-2">
                    <BarChart3 className="w-3 h-3" /> 传播动力学
                  </h4>
                  <p>基于改进的 SIRS 模型，实时计算信息渗透速率。</p>
                </div>
                <div className="space-y-2">
                  <h4 className="font-bold text-amber-500 uppercase tracking-widest flex items-center gap-2">
                    <Network className="w-3 h-3" /> 从众效应评估
                  </h4>
                  <p>利用 Asch 范式数字化模型，监测群体压力影响。</p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <SituationalAwarenessChart />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Deduction Control Section */}
        <Card className={cn("lg:col-span-6 p-8 space-y-8", industrialCardClass)}>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <Cpu className="w-5 h-5 text-blue-500" />
            </div>
            <h2 className="text-lg font-bold uppercase tracking-tight">推演控制中心 // CONTROL_UNIT</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
                  <BookOpen className="w-3 h-3" />
                  话题选择 (Topicbook)
                </div>
                <Select 
                  value={topicBook} 
                  onValueChange={(val) => {
                    setTopicBook(val);
                    simulationApi.updateConfig({ topics: [val] });
                  }}
                >
                  <SelectTrigger className="bg-bg-primary border-accent/20 text-text-primary">
                    <SelectValue placeholder="选择话题" value={topicBook} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="TOPIC_01">AI 伦理与未来</SelectItem>
                    <SelectItem value="TOPIC_02">全球气候变化</SelectItem>
                    <SelectItem value="TOPIC_03">数字货币监管</SelectItem>
                    <SelectItem value="TOPIC_04">元宇宙社交演化</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
                  <Users2 className="w-3 h-3" />
                  用户群体匹配
                </div>
                <Select 
                  value={userGroup} 
                  onValueChange={setUserGroup}
                >
                  <SelectTrigger className="bg-bg-primary border-accent/20 text-text-primary">
                    <SelectValue placeholder="选择群体" value={userGroup} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GROUP_A">激进主义群体 (Topic User A)</SelectItem>
                    <SelectItem value="GROUP_B">保守主义群体 (Topic User B)</SelectItem>
                    <SelectItem value="GROUP_C">中立理性群体 (Topic User C)</SelectItem>
                    <SelectItem value="GROUP_D">随机混合群体</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-6">
              <div className="space-y-4">
                <div className="flex justify-between items-end">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">Agent 规模</label>
                  <span className="text-xl font-mono font-bold text-accent">{agentCount[0].toLocaleString()}</span>
                </div>
                <Slider
                  value={agentCount}
                  onValueChange={setAgentCount}
                  min={10}
                  max={10000}
                  step={10}
                  className="py-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Button 
                  className={cn("h-12 rounded-lg font-bold gap-2 shadow-lg transition-all active:scale-95", 
                    status.running && !status.paused ? "bg-bg-tertiary hover:bg-border-strong text-text-primary" : "bg-accent hover:bg-accent-hover text-bg-primary shadow-accent/20"
                  )}
                  onClick={async () => {
                    try {
                      if (status.running && !status.paused) {
                        await simulationApi.pause();
                        setStatus({ ...status, paused: true });
                        toast.info('仿真已暂停');
                      } else {
                        await simulationApi.resume();
                        setStatus({ ...status, running: true, paused: false });
                        toast.success('仿真已启动');
                      }
                    } catch (e) {
                      toast.error('操作失败');
                    }
                  }}
                >
                  {status.running && !status.paused ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
                  {status.running && !status.paused ? '暂停' : '启动'}
                </Button>
                <Button 
                  variant="secondary" 
                  className="h-12 rounded-lg font-bold gap-2 border-accent/30 hover:bg-bg-tertiary transition-all active:scale-95"
                  disabled={isStepping}
                  onClick={async () => {
                    setIsStepping(true);
                    try {
                      await simulationApi.step();
                      const res = await simulationApi.getStatus();
                      setStatus(res.data);
                      toast.success('步进完成');
                    } catch (e) {
                      toast.error('步进失败');
                    } finally {
                      setIsStepping(false);
                    }
                  }}
                >
                  <StepForward className={cn("w-4 h-4", isStepping && "animate-spin")} />
                  单步
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* Guided Decision Section */}
        <Card className={cn("lg:col-span-6 p-8 space-y-8", industrialCardClass)}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent/10 border border-accent/20">
                <Lightbulb className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-lg font-bold uppercase tracking-tight">引导决策中心 // DECISION_HUB</h2>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="rounded-lg gap-2 border-accent/50 text-accent hover:bg-accent/10">
                <Wand2 className="w-3.5 h-3.5" />
                决策生成
              </Button>
              <Button size="sm" variant="outline" className="rounded-lg gap-2 border-accent/30">
                <UploadCloud className="w-3.5 h-3.5" />
                加载引导
              </Button>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <p className="text-xs text-text-tertiary leading-relaxed font-mono">
                [RECOMMENDATION] 针对当前态势，系统推荐以下干预策略:
              </p>
              <div className="space-y-3">
                <Button variant="outline" className="w-full justify-start h-auto py-3 px-4 rounded-lg border-accent/20 hover:border-accent/50 group bg-bg-primary/30">
                  <div className="text-left">
                    <p className="text-sm font-bold group-hover:text-accent transition-colors">引入中立信源</p>
                    <p className="text-[10px] text-text-muted font-mono">向极化社区推送 15% 的多样化观点</p>
                  </div>
                </Button>
                <Button variant="outline" className="w-full justify-start h-auto py-3 px-4 rounded-lg border-accent/20 hover:border-accent/50 group bg-bg-primary/30">
                  <div className="text-left">
                    <p className="text-sm font-bold group-hover:text-accent transition-colors">调整推荐权重</p>
                    <p className="text-[10px] text-text-muted font-mono">降低高热度争议内容的曝光增益</p>
                  </div>
                </Button>
              </div>
            </div>

            <div className="p-6 bg-bg-primary/50 rounded-lg border-2 border-accent/30 flex flex-col justify-center items-center text-center space-y-4 relative overflow-hidden">
              <AnimatePresence>
                {isSimulating && (
                  <motion.div 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 bg-accent/10 backdrop-blur-[4px] z-10 flex flex-col items-center justify-center"
                  >
                    <div className="relative w-20 h-20">
                      <motion.div 
                        className="absolute inset-0 border-4 border-accent border-t-transparent rounded-full"
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      />
                      <motion.div 
                        className="absolute inset-2 border-4 border-accent/30 border-b-transparent rounded-full"
                        animate={{ rotate: -360 }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                      />
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Cpu className="w-8 h-8 text-accent animate-pulse" />
                      </div>
                    </div>
                    <p className="text-[10px] font-bold text-accent mt-4 uppercase tracking-[0.3em] animate-pulse">SIMULATING_IMPACT...</p>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center text-accent border border-accent/30">
                <Layers className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-sm font-bold uppercase tracking-tight">策略模拟预览</h4>
                <p className="text-[10px] text-text-tertiary mt-1 font-mono">PREVIEW_STRATEGY_IMPACT_V1</p>
              </div>
              <Button 
                size="sm" 
                className="w-full rounded-lg bg-accent text-bg-primary font-bold hover:bg-accent-hover"
                onClick={handleSimulate}
                disabled={isSimulating}
              >
                开始模拟评估
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Analytics Merge Section */}
      <div className="pt-12 border-t border-accent/20 space-y-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="flex-1">
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-3 text-accent drop-shadow-[0_0_10px_rgba(0,242,255,0.3)]">
              <BarChart3 className="w-6 h-6" />
              深度指标监控 <span className="text-[10px] font-mono opacity-50 border border-accent/30 px-2 py-0.5 rounded ml-2 tracking-[0.3em]">METRICS_V2</span>
            </h2>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {metrics.map((m, i) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className={cn("p-6 hover:border-accent/50 transition-all group", industrialCardClass)}>
                <div className="flex justify-between items-start mb-4">
                  <div className="p-2 rounded-lg bg-bg-primary border border-border-default group-hover:border-accent/20 transition-colors">
                    <m.icon className={cn("w-5 h-5", m.color)} />
                  </div>
                  <Badge variant="outline" className={cn(
                    "text-[10px] gap-1",
                    m.up ? "text-emerald-500 border-emerald-500/20 bg-emerald-500/5" : "text-rose-500 border-rose-500/20 bg-rose-500/5"
                  )}>
                    {m.up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {m.trend}
                  </Badge>
                </div>
                <p className="text-xs font-bold text-text-tertiary uppercase tracking-widest mb-1">{m.label}</p>
                <h3 className="text-2xl font-bold tracking-tighter">{m.value}</h3>
              </Card>
            </motion.div>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Polarization Detail */}
          <Card className={cn("p-6 flex flex-col h-[300px]", industrialCardClass)}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-secondary flex items-center gap-2">
                <Activity className="w-3 h-3 text-rose-500" />
                极化演化
              </h3>
            </div>
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorPol2" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="currentStep" hide />
                  <YAxis stroke="#52525b" fontSize={8} tickLine={false} axisLine={false} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', fontSize: '10px' }}
                  />
                  <Area type="monotone" dataKey="polarization" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorPol2)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Velocity Trend */}
          <Card className={cn("p-6 h-[300px]", industrialCardClass)}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-secondary flex items-center gap-2">
                <TrendingUp className="w-3 h-3 text-emerald-500" />
                传播通量
              </h3>
            </div>
            <div className="h-full pb-8">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                  <XAxis dataKey="currentStep" hide />
                  <YAxis stroke="#52525b" fontSize={8} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', fontSize: '10px' }} />
                  <Line type="stepAfter" dataKey="propagation" stroke="#10b981" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Opinion Matrix */}
          <Card className={cn("p-6 flex flex-col h-[300px]", industrialCardClass)}>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-secondary flex items-center gap-2 mb-4">
              <PieChartIcon className="w-3 h-3 text-accent" />
              观点分布
            </h3>
            <div className="flex-1 min-h-0 flex flex-col justify-center">
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={opinionDistribution} layout="vertical" margin={{ left: -20 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" stroke="#fafafa" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: 'transparent' }} contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', fontSize: '10px' }} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                    {opinionDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-4 space-y-2">
                {opinionDistribution.map((d, i) => (
                  <div key={i} className="flex justify-between items-center p-2 rounded-lg bg-bg-primary/50 border border-accent/20">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }}></div>
                      <span className="text-[10px] font-bold text-text-secondary">{d.name}</span>
                    </div>
                    <span className="text-xs font-mono font-bold">{d.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

