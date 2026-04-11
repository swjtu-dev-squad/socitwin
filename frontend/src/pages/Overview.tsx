import { useEffect, useState, useMemo } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Button, Badge, Slider, Progress, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, ScrollArea } from '@/components/ui';
import { useNavigate } from 'react-router-dom';
import { simulationApi } from '@/lib/api';
import {
  Users,
  Activity,
  Zap,
  TrendingUp,
  Cpu,
  Eye,
  Play,
  Pause,
  StepForward,
  ShieldAlert,
  Lightbulb,
  Share2,
  Database,
  BookOpen,
  Users2,
  Wand2,
  Info,
  Target,
  BarChart3,
  Network,
  ArrowUpRight,
  ArrowDownRight,
  AlertCircle,
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
  const [recsys, setRecsys] = useState('GLOBAL_Trending');
  const [selectedTopic, setSelectedTopic] = useState<string>('ai-employment');
  const [userGroupMode, setUserGroupMode] = useState<'follow' | 'custom'>('follow');
  const [showAlgorithm, setShowAlgorithm] = useState(false);
  const [samplingRate, setSamplingRate] = useState([10]); // Default 10% sampling
  const [availableTopics, setAvailableTopics] = useState<Array<{ id: string; filename: string; seed_posts: string[]; agent_profiles_count: number }>>([]);
  const [opinionDistribution, setOpinionDistribution] = useState<Array<{ name: string; value: number; count: number; color: string }>>([]);
  const [herdIndexTrend, setHerdIndexTrend] = useState<Array<{ step: number; herdIndex: number }>>([]);
  const [interventionProfiles, setInterventionProfiles] = useState<Array<{
    name: string;
    description: string;
    user_name_prefix: string;
    bio: string;
    system_message: string;
    initial_posts: string[];
    comment_style: string;
  }>>([]);
  const [selectedInterventionTypes, setSelectedInterventionTypes] = useState<string[]>([]);
  const [interventionCount, setInterventionCount] = useState(1);
  const [isIntervening, setIsIntervening] = useState(false);
  const [interventionResult, setInterventionResult] = useState<any>(null);
  
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

  // Load available topics from backend
  useEffect(() => {
    const fetchTopics = async () => {
      try {
        const res = await simulationApi.getTopics();
        if (res.data.status === 'ok') {
          setAvailableTopics(res.data.topics);
          // Set default topic if none selected
          if (!selectedTopic && res.data.topics.length > 0) {
            setSelectedTopic(res.data.topics[0].id);
          }
        }
      } catch (error) {
        console.error('Failed to fetch topics:', error);
      }
    };
    fetchTopics();
  }, []);

  // Extract real data from history for trend charts
  const chartData: any[] = useMemo(() => {
    if (!history || history.length === 0) {
      // Return empty array if no history
      return [];
    }

    return history.map((entry, index) => ({
      currentStep: entry.currentStep || index,
      polarization: entry.polarization || 0,
      propagation: ((entry.propagation?.scale || 0) / Math.max((entry.activeAgents || status.activeAgents || 1), 1)), // Normalize scale by active agents
      herding: entry.herdHhi || 0,
    }));
  }, [history, status.activeAgents]);

  const stats = [
    { label: '活跃 Agents', value: (status.activeAgents || 0).toLocaleString(), icon: Users, color: 'text-accent', path: '/agents' },
    { label: '当前步数', value: (status.currentStep || 0).toLocaleString(), icon: Zap, color: 'text-amber-400', path: '/overview' },
  ];

  // Industrial Border Style
  const industrialCardClass = "bg-bg-secondary border-2 border-accent/30 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-2 before:h-2 before:border-t-2 before:border-l-2 before:border-accent after:absolute after:bottom-0 after:right-0 after:w-2 after:h-2 after:border-b-2 after:border-r-2 after:border-accent";

  // Cognitive Warning Logic (based on real data)
  const threatLevel = useMemo(() => {
    // Use current status if available, otherwise fall back to latest history entry
    const currentPol = status.polarization || 0;
    const currentProp = ((status.propagation?.scale || 0) / Math.max(status.activeAgents || 1, 1));
    const currentHerd = status.herdHhi || 0;
    const avg = (currentPol + currentProp + currentHerd) / 3;

    if (avg > 0.7) return { label: '高危', color: 'text-rose-500', bg: 'bg-rose-500/10', border: 'border-rose-500/20' };
    if (avg > 0.4) return { label: '中等', color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/20' };
    return { label: '安全', color: 'text-accent', bg: 'bg-accent/10', border: 'border-accent/20' };
  }, [status]);

  // Load opinion distribution from backend
  useEffect(() => {
    const fetchOpinionDistribution = async () => {
      try {
        const res = await simulationApi.getOpinionDistribution();
        if (res.data && res.data.distribution) {
          // Map backend data to frontend format with colors
          const colorMap: Record<string, string> = {
            'Left': '#f43f5e',
            'Center': '#71717a',
            'Right': '#3b82f6'
          };
          const nameMap: Record<string, string> = {
            'Left': '极左',
            'Center': '中立',
            'Right': '极右'
          };
          const distribution = res.data.distribution.map((item: { name: string; value: number; count: number }) => ({
            ...item,
            name: nameMap[item.name] || item.name,
            color: colorMap[item.name] || '#71717a'
          }));
          setOpinionDistribution(distribution);
        }
      } catch (error) {
        console.error('Failed to fetch opinion distribution:', error);
      }
    };
    fetchOpinionDistribution();
    const interval = setInterval(fetchOpinionDistribution, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  // Load herd index trend from backend
  useEffect(() => {
    const fetchHerdIndex = async () => {
      try {
        const res = await simulationApi.getHerdIndex();
        if (res.data && res.data.trend) {
          setHerdIndexTrend(res.data.trend);
        }
      } catch (error) {
        console.error('Failed to fetch herd index:', error);
      }
    };
    fetchHerdIndex();
    const interval = setInterval(fetchHerdIndex, 5000);
    return () => clearInterval(interval);
  }, []);

  // Load intervention profiles from backend
  useEffect(() => {
    const fetchInterventionProfiles = async () => {
      try {
        const res = await simulationApi.getInterventionProfiles();
        if (res.data && res.data.intervention_profiles) {
          setInterventionProfiles(res.data.intervention_profiles);
        }
      } catch (error) {
        console.error('Failed to fetch intervention profiles:', error);
      }
    };
    fetchInterventionProfiles();
  }, []);

  // Handle intervention type selection
  const toggleInterventionType = (typeName: string) => {
    setSelectedInterventionTypes(prev =>
      prev.includes(typeName)
        ? prev.filter(t => t !== typeName)
        : [...prev, typeName]
    );
  };

  // Handle applying intervention
  const handleApplyIntervention = async () => {
    if (selectedInterventionTypes.length === 0) {
      toast.error('请至少选择一种干预类型');
      return;
    }

    setIsIntervening(true);
    try {
      const res = await simulationApi.addControlledAgentsBatch(
        selectedInterventionTypes,
        true  // initial_step
      );

      if (res.data && res.data.status === 'ok') {
        setInterventionResult(res.data);
        toast.success(`成功添加 ${res.data.total || 0} 个受控 agents`);

        // Refresh status
        const statusRes = await simulationApi.getStatus();
        setStatus(statusRes.data);
      } else {
        toast.error('干预失败');
      }
    } catch (error) {
      console.error('Intervention failed:', error);
      toast.error('干预请求失败');
    } finally {
      setIsIntervening(false);
    }
  };

  // Calculate metrics based on real data
  const metrics = useMemo(() => {
    // Calculate trends based on history
    let polTrend = '+0.0%';
    let propTrend = '+0';
    let herdTrend = '+0.0%';

    if (history.length >= 2) {
      const prev = history[history.length - 2];
      const curr = history[history.length - 1];

      const polChangeValue = (curr.polarization - prev.polarization) * 100;
      polTrend = `${polChangeValue >= 0 ? '+' : ''}${polChangeValue.toFixed(1)}%`;

      // 使用 propagation.scale 计算传播规模趋势
      const prevPropScale = (prev.propagation?.scale || 0);
      const currPropScale = (curr.propagation?.scale || 0);
      const propChangeValue = currPropScale - prevPropScale;
      propTrend = `${propChangeValue >= 0 ? '+' : ''}${propChangeValue} 人`;

      const herdChangeValue = ((curr.herdHhi || 0) - (prev.herdHhi || 0)) * 100;
      herdTrend = `${herdChangeValue >= 0 ? '+' : ''}${herdChangeValue.toFixed(1)}%`;
    }

    return [
      {
        label: '群体极化率',
        value: `${(status.polarization * 100).toFixed(1)}%`,
        trend: polTrend,
        up: !polTrend.startsWith('-'),
        icon: Zap,
        color: 'text-rose-500'
      },
      {
        label: '信息传播规模',
        value: `${status.propagation?.scale || 0} 人`,
        trend: propTrend,
        up: !propTrend.startsWith('-'),
        icon: TrendingUp,
        color: 'text-emerald-500'
      },
      {
        label: '从众效应指数',
        value: `${((status.herdHhi || 0) * 100).toFixed(1)}%`,
        trend: herdTrend,
        up: !herdTrend.startsWith('-'),
        icon: Users,
        color: 'text-blue-500'
      },
      {
        label: '活跃节点密度',
        value: status.activeAgents > 0 ? (status.activeAgents / (status.agents?.length || 1)).toFixed(2) : '0.00',
        trend: history.length >= 2 ?
              (((history[history.length - 1].activeAgents || 0) - (history[history.length - 2].activeAgents || 0)) >= 0 ? '+0.01' : '-0.01') :
              '+0.00',
        up: true,
        icon: Activity,
        color: 'text-amber-500'
      },
    ];
  }, [status, history]);

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
                // 只更新本地状态，不调用 API
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
                    <span className="text-rose-500">{(status.polarization * 100).toFixed(0)}</span>
                  </div>
                  <Progress value={status.polarization * 100} className="h-1 bg-bg-tertiary" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>传播规模</span>
                    <span className="text-emerald-500">{status.propagation?.scale || 0}</span>
                  </div>
                  <Progress value={Math.min(((status.propagation?.scale || 0) / Math.max(status.activeAgents || 1, 1)) * 100, 100)} className="h-1 bg-bg-tertiary" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>从众效应</span>
                    <span className="text-amber-500">{((status.herdHhi || 0) * 100).toFixed(0)}</span>
                  </div>
                  <Progress value={(status.herdHhi || 0) * 100} className="h-1 bg-bg-tertiary" />
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
                  话题选择
                </div>
                <Select
                  value={selectedTopic}
                  onValueChange={(val) => {
                    setSelectedTopic(val);
                    // 只更新本地状态，不调用 API
                  }}
                >
                  <SelectTrigger className="bg-bg-primary border-accent/20 text-text-primary">
                    <SelectValue placeholder="选择话题" value={selectedTopic} />
                  </SelectTrigger>
                  <SelectContent>
                    {availableTopics.map((topic: { id: string; filename: string; seed_posts: string[]; agent_profiles_count: number }) => (
                      <SelectItem key={topic.id} value={topic.id}>
                        {topic.id.replace(/-/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                        <span className="text-xs text-text-muted ml-2">
                          ({topic.agent_profiles_count} profiles)
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
                  <Users2 className="w-3 h-3" />
                  用户群体匹配
                </div>
                <Select
                  value={userGroupMode}
                  onValueChange={(val: 'follow' | 'custom') => setUserGroupMode(val)}
                >
                  <SelectTrigger className="bg-bg-primary border-accent/20 text-text-primary">
                    <SelectValue placeholder="选择模式" value={userGroupMode} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="follow">
                      跟随话题配置
                      <span className="text-xs text-text-muted ml-2 block">
                        使用话题预定义的 Agent Profiles
                      </span>
                    </SelectItem>
                    <SelectItem value="custom" disabled>
                      自定义数据集
                      <span className="text-xs text-text-muted ml-2 block">
                        (即将推出)
                      </span>
                    </SelectItem>
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
                  onValueChange={(val) => {
                    setAgentCount(val);
                    // 只更新本地状态，不调用 API
                  }}
                  min={10}
                  max={1000}
                  step={10}
                  className="py-2"
                />
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-end">
                  <div className="flex flex-col">
                    <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">采样率</label>
                    <span className="text-[9px] text-text-muted font-mono mt-0.5">每步活跃 Agents 比例</span>
                  </div>
                  <span className="text-xl font-mono font-bold text-accent">{samplingRate[0]}%</span>
                </div>
                <Slider
                  value={samplingRate}
                  onValueChange={(val) => {
                    setSamplingRate(val);
                    // 只更新本地状态，不调用 API
                  }}
                  min={1}
                  max={100}
                  step={1}
                  className="py-2"
                />
                <div className="flex justify-between text-[9px] text-text-muted font-mono">
                  <span>1% (采样)</span>
                  <span>100% (全部)</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <Button
                  className={cn("h-12 rounded-lg font-bold gap-2 shadow-lg transition-all active:scale-95",
                    status.running && !status.paused ? "bg-bg-tertiary hover:bg-border-strong text-text-primary" : "bg-accent hover:bg-accent-hover text-bg-primary shadow-accent/20"
                  )}
                  onClick={async () => {
                    try {
                      if (status.running && !status.paused) {
                        // 暂停
                        await simulationApi.pause();
                        setStatus({ ...status, paused: true });
                        toast.info('仿真已暂停');
                      } else {
                        // 启动：先应用配置，再启动
                        await simulationApi.updateConfig({
                          platform: subscriptionSource,
                          recsys: recsys,
                          agentCount: agentCount[0],
                          topics: [selectedTopic],
                          regions: [],
                          sampling_config: {
                            enabled: samplingRate[0] < 100,
                            rate: samplingRate[0] / 100,
                            strategy: 'random',
                            min_active: 5,
                            seed: 42
                          }
                        });
                        setStatus({ ...status, running: true, paused: false });
                        toast.success(`仿真已启动: ${selectedTopic} (${agentCount[0]} agents, ${samplingRate[0]}% sampling)`);
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

        {/* Guided Decision Section - Intervention Hub */}
        <Card className={cn("lg:col-span-6 p-8 space-y-6", industrialCardClass)}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent/10 border border-accent/20">
                <Lightbulb className="w-5 h-5 text-accent" />
              </div>
              <h2 className="text-lg font-bold uppercase tracking-tight">干预决策中心 // INTERVENTION_HUB</h2>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="text-[10px] font-mono bg-accent/10 text-accent border-accent/20">
                Step: {status.currentStep}
              </Badge>
            </div>
          </div>

          <div className="space-y-4">
            {/* Intervention Type Selection */}
            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                选择干预类型
              </label>
              <ScrollArea className="h-[200px] rounded-lg border border-accent/20 bg-bg-primary/50">
                <div className="p-3 space-y-2">
                  {interventionProfiles.map((profile) => (
                    <div
                      key={profile.name}
                      className={cn(
                        "p-3 rounded-lg border-2 cursor-pointer transition-all",
                        selectedInterventionTypes.includes(profile.name)
                          ? "bg-accent/10 border-accent"
                          : "bg-bg-primary border-border-default hover:border-accent/30"
                      )}
                      onClick={() => toggleInterventionType(profile.name)}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <div className={cn(
                              "w-4 h-4 rounded border-2 flex items-center justify-center",
                              selectedInterventionTypes.includes(profile.name)
                                ? "bg-accent border-accent"
                                : "border-text-muted"
                            )}>
                              {selectedInterventionTypes.includes(profile.name) && (
                                <div className="w-2 h-2 rounded-full bg-bg-primary" />
                              )}
                            </div>
                            <span className="text-sm font-bold text-text-primary">
                              {profile.description}
                            </span>
                          </div>
                          <p className="text-[10px] text-text-muted font-mono mt-1">
                            {profile.comment_style}
                          </p>
                          <p className="text-[9px] text-text-tertiary mt-2 line-clamp-2">
                            {profile.initial_posts[0]}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Intervention Count Input */}
            <div className="space-y-3">
              <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                每种类型的 Agent 数量
              </label>
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 rounded-lg p-0 border-accent/30"
                  onClick={() => setInterventionCount(Math.max(1, interventionCount - 1))}
                  disabled={interventionCount <= 1}
                >
                  -
                </Button>
                <div className="flex-1 text-center">
                  <span className="text-2xl font-mono font-bold text-accent">{interventionCount}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 rounded-lg p-0 border-accent/30"
                  onClick={() => setInterventionCount(Math.min(10, interventionCount + 1))}
                  disabled={interventionCount >= 10}
                >
                  +
                </Button>
              </div>
              <p className="text-[9px] text-text-tertiary font-mono text-center">
                总计将添加: {selectedInterventionTypes.length * interventionCount} 个 agents
              </p>
            </div>

            {/* Apply Intervention Button */}
            <Button
              className={cn(
                "w-full h-12 rounded-lg font-bold gap-2 transition-all",
                selectedInterventionTypes.length === 0 || isIntervening
                  ? "bg-bg-tertiary text-text-muted cursor-not-allowed"
                  : "bg-accent hover:bg-accent-hover text-bg-primary shadow-accent/20"
              )}
              onClick={handleApplyIntervention}
              disabled={selectedInterventionTypes.length === 0 || isIntervening}
            >
              {isIntervening ? (
                <>
                  <Cpu className="w-4 h-4 animate-spin" />
                  正在添加干预 Agents...
                </>
              ) : (
                <>
                  <Wand2 className="w-4 h-4" />
                  应用干预 ({selectedInterventionTypes.length} 种类型 × {interventionCount})
                </>
              )}
            </Button>

            {/* Intervention Result */}
            {interventionResult && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20 space-y-2"
              >
                <div className="flex items-center gap-2 text-emerald-500">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-bold uppercase tracking-widest">干预成功</span>
                </div>
                <div className="text-[10px] text-text-secondary space-y-1">
                  <p>✓ 已添加 {interventionResult.total || 0} 个受控 agents</p>
                  {interventionResult.created_agents && interventionResult.created_agents.length > 0 && (
                    <div className="mt-2 space-y-1">
                      <p className="font-mono text-[9px] text-text-tertiary uppercase">创建的 Agents:</p>
                      {interventionResult.created_agents.slice(0, 5).map((agent: any, idx: number) => (
                        <div key={idx} className="flex items-center gap-2 text-[9px] font-mono">
                          <span className="text-accent">ID:{agent.agent_id}</span>
                          <span className="text-text-primary">{agent.user_name}</span>
                          <span className="text-text-tertiary">({agent.type})</span>
                        </div>
                      ))}
                      {interventionResult.created_agents.length > 5 && (
                        <p className="text-[9px] text-text-tertiary italic">
                          ... 还有 {interventionResult.created_agents.length - 5} 个 agents
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
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
              {chartData.length > 0 ? (
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
              ) : (
                <div className="flex items-center justify-center h-full text-text-tertiary text-xs">
                  等待数据...
                </div>
              )}
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
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                    <XAxis dataKey="currentStep" hide />
                    <YAxis stroke="#52525b" fontSize={8} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', fontSize: '10px' }} />
                    <Line type="stepAfter" dataKey="propagation" stroke="#10b981" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-text-tertiary text-xs">
                  等待数据...
                </div>
              )}
            </div>
          </Card>

          {/* Opinion Matrix */}
          <Card className={cn("p-6 flex flex-col h-[300px]", industrialCardClass)}>
            <h3 className="text-[10px] font-bold uppercase tracking-widest text-text-secondary flex items-center gap-2 mb-4">
              <PieChartIcon className="w-3 h-3 text-accent" />
              观点分布
            </h3>
            <div className="flex-1 min-h-0 flex flex-col justify-center">
              {opinionDistribution.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={120}>
                    <BarChart data={opinionDistribution} layout="vertical" margin={{ left: -20 }}>
                      <XAxis type="number" hide />
                      <YAxis dataKey="name" type="category" stroke="#fafafa" fontSize={10} tickLine={false} axisLine={false} />
                      <Tooltip cursor={{ fill: 'transparent' }} contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', fontSize: '10px' }} />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                        {opinionDistribution.map((entry: { name: string; value: number; count: number; color: string }, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="mt-4 space-y-2">
                    {opinionDistribution.map((d: { name: string; value: number; count: number; color: string }, i: number) => (
                      <div key={i} className="flex justify-between items-center p-2 rounded-lg bg-bg-primary/50 border border-accent/20">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }}></div>
                          <span className="text-[10px] font-bold text-text-secondary">{d.name}</span>
                        </div>
                        <span className="text-xs font-mono font-bold">{d.value}%</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-full text-text-tertiary text-xs">
                  等待数据...
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

