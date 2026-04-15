import { useEffect, useState, useMemo } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Button, Badge, Slider, Progress, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui';
import { useLocation, useNavigate } from 'react-router-dom';
import { simulationApi } from '@/lib/api';
import {
  useSimulationStatusLightweight,
  useTopics,
  useMetricsHistory,
  useStepDrivenMetrics
} from '@/hooks/useSimulationData';
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
  Share2,
  BookOpen,
  RotateCcw,
  Info,
  BarChart3,
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
import type { DatasetPlatform } from '@/components/SubscriptionPanel';

function normalizeSimulationStatus(backendData: any): any {
  return {
    ...backendData,
    running: backendData.state === 'running',
    paused: backendData.state === 'paused',
    originalState: backendData.state,
    currentStep: backendData.current_step,
    currentRound: backendData.current_round,
    activeAgents: backendData.active_agents,
    totalPosts: backendData.total_posts,
    totalInteractions: backendData.total_interactions,
    agentCount: backendData.agent_count,
    totalSteps: backendData.total_steps,
    platform: backendData.platform,
    recsys: backendData.recsys,
    topics: backendData.topics,
    regions: backendData.regions,
  };
}

function getRequestErrorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '请求失败';
  }

  const maybeError = error as any;
  return (
    maybeError?.response?.data?.detail ||
    maybeError?.response?.data?.message ||
    maybeError?.message ||
    '请求失败'
  );
}

export default function Overview() {
  const { status, setStatus, isStepping, setIsStepping } = useSimulationStore();
  const navigate = useNavigate();
  const location = useLocation();
  const initialFilters =
    (location.state as { selectedPlatform?: DatasetPlatform; selectedTopic?: string } | null) ?? null;

  // Use custom hooks for data fetching
  const { data: statusData, currentStep, refetch: refetchStatus } = useSimulationStatusLightweight(2000);
  const [selectedPlatform, setSelectedPlatform] = useState<DatasetPlatform>(
    initialFilters?.selectedPlatform ?? 'twitter',
  );
  const { data: topics, isLoading: topicsLoading } = useTopics(selectedPlatform);
  const { data: chartHistory, isLoading: historyLoading } = useMetricsHistory(currentStep);
  const { latestMetrics } = useStepDrivenMetrics(currentStep || 0);

  // Use the latest status from hook if available, otherwise fall back to store
  const currentStatus = statusData || status;

  // Derive opinion distribution from step-driven polarization data
  const opinionDistribution = useMemo(() => {
    if (!latestMetrics?.polarization?.agent_polarization) {
      return [];
    }

    const directionMap: Record<string, string> = {
      'EXTREME_CONSERVATIVE': 'Right',
      'MODERATE_CONSERVATIVE': 'Right',
      'NEUTRAL': 'Center',
      'MODERATE_PROGRESSIVE': 'Left',
      'EXTREME_PROGRESSIVE': 'Left',
    };

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

    // Count agents in each category
    const counts: Record<string, number> = { 'Left': 0, 'Center': 0, 'Right': 0 };
    latestMetrics.polarization.agent_polarization.forEach(agent => {
      const category = directionMap[agent.direction] || 'Center';
      counts[category]++;
    });

    // Calculate percentages
    const total = latestMetrics.polarization.agent_polarization.length;
    return Object.entries(counts).map(([category, count]) => ({
      name: nameMap[category] || category,
      value: total > 0 ? Math.round((count / total) * 100) : 0,
      count,
      color: colorMap[category] || '#71717a'
    }));
  }, [latestMetrics?.polarization]);

  // Local state for UI controls
  const [agentCount, setAgentCount] = useState([10]); // 默认10个agents
  const [selectedTopic, setSelectedTopic] = useState<string>(initialFilters?.selectedTopic ?? '');
  const [showAlgorithm, setShowAlgorithm] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const selectedTopicMeta = useMemo(
    () => topics.find((topic) => topic.id === selectedTopic) || null,
    [topics, selectedTopic],
  );
  const selectedTopicLabel = selectedTopicMeta?.name || '';
  const availableOriginalUserCount = selectedTopicMeta?.user_count ?? 0;
  const originalUserSourceLabel = `原始用户 (${availableOriginalUserCount})`;
  const platformLabelMap: Record<DatasetPlatform, string> = {
    twitter: 'X / Twitter',
    reddit: 'Reddit',
    tiktok: 'TikTok',
    instagram: 'Instagram',
    facebook: 'Facebook',
  };
  const [selectedUserSource, setSelectedUserSource] = useState<'topic-original'>('topic-original');
  const maxUserCount = availableOriginalUserCount;
  const isSupportedSimulationPlatform =
    selectedPlatform === 'twitter' || selectedPlatform === 'reddit';

  // Update store status when hook data changes
  useEffect(() => {
    if (statusData) {
      setStatus(statusData);
    }
  }, [statusData, setStatus]);

  // Keep topic selection aligned with the currently selected platform
  useEffect(() => {
    if (topics.length === 0) {
      setSelectedTopic('');
      return;
    }

    const matchedTopic = topics.some((topic) => topic.id === selectedTopic);
    if (!matchedTopic) {
      setSelectedTopic(topics[0].id);
    }
  }, [topics, selectedTopic]);

  useEffect(() => {
    setAgentCount((prev) => {
      if (availableOriginalUserCount <= 0) {
        return prev[0] === 0 ? prev : [0];
      }

      const nextValue = Math.min(Math.max(prev[0], 1), availableOriginalUserCount);
      return nextValue === prev[0] ? prev : [nextValue];
    });
  }, [availableOriginalUserCount]);

  // Extract real data from history for trend charts
  // NEW: Use database history (step-based) instead of store history (time-based)
  const chartData: any[] = useMemo(() => {
    if (!chartHistory || chartHistory.length === 0) {
      return [];
    }

    // Map database history to chart format
    return chartHistory.map(point => ({
      currentStep: point.step,
      polarization: point.polarization || 0,
      propagation: point.propagation || 0,
      herding: point.herdEffect || 0,
    }));
  }, [chartHistory]);

  const stats = [
    { label: '活跃 Agents', value: (currentStatus.activeAgents || 0).toLocaleString(), icon: Users, color: 'text-accent', path: '/agents' },
    { label: '当前步数', value: (currentStatus.currentStep || 0).toLocaleString(), icon: Zap, color: 'text-amber-400', path: '/overview' },
  ];

  // Industrial Border Style
  const industrialCardClass = "bg-bg-secondary border-2 border-accent/30 relative overflow-hidden before:absolute before:top-0 before:left-0 before:w-2 before:h-2 before:border-t-2 before:border-l-2 before:border-accent after:absolute after:bottom-0 after:right-0 after:w-2 after:h-2 after:border-b-2 after:border-r-2 before:border-accent";

  // Cognitive Warning Logic (based on historical metrics from database)
  const threatLevel = useMemo(() => {
    const currentPol = latestMetrics?.polarization?.average_magnitude ?? 0;
    const currentProp = (latestMetrics?.propagation?.scale || 0) / Math.max(currentStatus.activeAgents || 1, 1);
    const currentHerd = latestMetrics?.herdEffect?.conformity_index ?? 0;
    const avg = (currentPol + currentProp + currentHerd) / 3;

    if (avg > 0.7) return { label: '高危', color: 'text-rose-500', bg: 'bg-rose-500/10', border: 'border-rose-500/20' };
    if (avg > 0.4) return { label: '中等', color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/20' };
    return { label: '安全', color: 'text-accent', bg: 'bg-accent/10', border: 'border-accent/20' };
  }, [latestMetrics, currentStatus.activeAgents]);

  // Calculate core metrics based on historical data from database (step-driven)
  const coreMetrics = useMemo(() => {
    // Debug: Log latestMetrics and chartHistory
    console.log('[Overview] latestMetrics:', latestMetrics);
    console.log('[Overview] chartHistory length:', chartHistory.length);
    console.log('[Overview] chartHistory last entry:', chartHistory[chartHistory.length - 1]);

    // Priority: Use latestMetrics if available, otherwise fall back to latest entry from chartHistory
    let polValue = null;
    let propValue = null;
    let herdValue = null;

    // Try to get from latestMetrics first
    if (latestMetrics?.polarization?.average_magnitude !== undefined && latestMetrics?.polarization?.average_magnitude !== null) {
      polValue = latestMetrics.polarization.average_magnitude;
    }
    if (latestMetrics?.propagation?.scale !== undefined && latestMetrics?.propagation?.scale !== null) {
      propValue = latestMetrics.propagation.scale;
    }
    if (latestMetrics?.herdEffect?.conformity_index !== undefined && latestMetrics?.herdEffect?.conformity_index !== null) {
      herdValue = latestMetrics.herdEffect.conformity_index;
    }

    // Fall back to chartHistory if latestMetrics doesn't have data
    if (chartHistory.length > 0) {
      const latestEntry = chartHistory[chartHistory.length - 1];
      if (polValue === null && latestEntry.polarization !== undefined) {
        polValue = latestEntry.polarization;
      }
      if (propValue === null && latestEntry.propagation !== undefined) {
        propValue = latestEntry.propagation;
      }
      if (herdValue === null && latestEntry.herdEffect !== undefined) {
        herdValue = latestEntry.herdEffect;
      }
    }

    console.log('[Overview] Final values - polValue:', polValue, 'propValue:', propValue, 'herdValue:', herdValue);

    // Calculate trend from database history (not from store history with real-time values)
    let polTrend = '--';
    let propTrend = '--';
    let herdTrend = '--';

    if (chartHistory.length >= 2) {
      const prev = chartHistory[chartHistory.length - 2];
      const curr = chartHistory[chartHistory.length - 1];

      const polChangeValue = ((curr.polarization || 0) - (prev.polarization || 0)) * 100;
      polTrend = `${polChangeValue >= 0 ? '+' : ''}${polChangeValue.toFixed(1)}%`;

      const propChangeValue = (curr.propagation || 0) - (prev.propagation || 0);
      propTrend = `${propChangeValue >= 0 ? '+' : ''}${propChangeValue} 人`;

      const herdChangeValue = ((curr.herdEffect || 0) - (prev.herdEffect || 0)) * 100;
      herdTrend = `${herdChangeValue >= 0 ? '+' : ''}${herdChangeValue.toFixed(1)}%`;
    }

    return [
      {
        label: '群体极化率',
        value: polValue !== null ? `${(polValue * 100).toFixed(1)}%` : '--',
        trend: polTrend,
        up: polValue !== null && !polTrend.startsWith('-'),
        icon: Zap,
        color: 'text-rose-500'
      },
      {
        label: '信息传播规模',
        value: propValue !== null ? `${propValue} 人` : '--',
        trend: propTrend,
        up: propValue !== null && !propTrend.startsWith('-'),
        icon: TrendingUp,
        color: 'text-emerald-500'
      },
      {
        label: '从众效应指数',
        value: herdValue !== null ? `${(herdValue * 100).toFixed(1)}%` : '--',
        trend: herdTrend,
        up: herdValue !== null && !herdTrend.startsWith('-'),
        icon: Users,
        color: 'text-blue-500'
      },
    ];
  }, [latestMetrics, chartHistory]);

  // Calculate active node density metric (updates with status polling)
  const activeNodeDensityMetric = useMemo(() => {
    return {
      label: '活跃节点密度',
      value: currentStatus.activeAgents > 0 ? (currentStatus.activeAgents / (currentStatus.agents?.length || 1)).toFixed(2) : '--',
      trend: '--',
      up: true,
      icon: Activity,
      color: 'text-amber-500'
    };
  }, [currentStatus.activeAgents, currentStatus.agents]);

  // Combine core metrics and active node density
  const metrics = [...coreMetrics, activeNodeDensityMetric];

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
          <div className="flex items-center gap-3">
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStatus.state || currentStatus.originalState || (currentStatus.running ? 'running' : 'idle')}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                className={cn(
                  "h-9 flex items-center gap-2 px-4 rounded-lg border-2 text-xs font-bold uppercase tracking-widest",
                  // Use state field if available, otherwise fall back to running/paused
                  (currentStatus.state === 'running' || currentStatus.running) && currentStatus.state !== 'paused' && !currentStatus.paused ? "bg-accent/10 border-accent/50 text-accent shadow-[0_0_15px_rgba(0,242,255,0.2)]" :
                  (currentStatus.state === 'paused' || currentStatus.paused) ? "bg-amber-500/10 border-amber-500/50 text-amber-500" :
                  currentStatus.state === 'complete' ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-500" :
                  currentStatus.state === 'error' ? "bg-rose-500/10 border-rose-500/50 text-rose-500" :
                  "bg-bg-tertiary border-border-default text-text-tertiary"
                )}
              >
                <div className={cn("w-2 h-2 rounded-full",
                  (currentStatus.state === 'running' || currentStatus.running) && currentStatus.state !== 'paused' && !currentStatus.paused ? "bg-accent animate-pulse shadow-[0_0_8px_#00f2ff]" :
                  (currentStatus.state === 'paused' || currentStatus.paused) ? "bg-amber-500" :
                  currentStatus.state === 'complete' ? "bg-emerald-500" :
                  currentStatus.state === 'error' ? "bg-rose-500" :
                  "bg-text-muted"
                )}></div>
                {
                  // Use state field if available
                  currentStatus.state ?
                    (currentStatus.state === 'running' ? 'Active' :
                     currentStatus.state === 'paused' ? 'Paused' :
                     currentStatus.state === 'complete' ? 'Complete' :
                     currentStatus.state === 'error' ? 'Error' :
                     currentStatus.state === 'ready' ? 'Ready' :
                     currentStatus.state.charAt(0).toUpperCase() + currentStatus.state.slice(1))
                    :
                    // Fall back to running/paused for compatibility
                    (currentStatus.running && !currentStatus.paused ? 'Active' : currentStatus.paused ? 'Paused' : 'Idle')
                }
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
                    <span className="text-rose-500">{((latestMetrics?.polarization?.average_magnitude ?? 0) * 100).toFixed(0)}</span>
                  </div>
                  <Progress value={(latestMetrics?.polarization?.average_magnitude ?? 0) * 100} className="h-1 bg-bg-tertiary" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>传播规模</span>
                    <span className="text-emerald-500">{latestMetrics?.propagation?.scale || 0}</span>
                  </div>
                  <Progress value={Math.min(((latestMetrics?.propagation?.scale || 0) / Math.max(currentStatus.activeAgents || 1, 1)) * 100, 100)} className="h-1 bg-bg-tertiary" />
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-[9px] font-bold text-text-tertiary uppercase">
                    <span>从众效应</span>
                    <span className="text-amber-500">{((latestMetrics?.herdEffect?.conformity_index ?? 0) * 100).toFixed(0)}</span>
                  </div>
                  <Progress value={(latestMetrics?.herdEffect?.conformity_index ?? 0) * 100} className="h-1 bg-bg-tertiary" />
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
                  <Cpu className="w-3 h-3" />
                  平台选择
                </div>
                <select
                  value={selectedPlatform}
                  onChange={(e) => setSelectedPlatform(e.target.value as DatasetPlatform)}
                  className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-bg-primary border-accent/20 text-text-primary"
                >
                  <option value="twitter">X / Twitter</option>
                  <option value="reddit">Reddit</option>
                  <option value="tiktok">TikTok</option>
                  <option value="instagram">Instagram</option>
                  <option value="facebook">Facebook</option>
                </select>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
                  <BookOpen className="w-3 h-3" />
                  话题选择
                </div>
                <select
                  value={selectedTopic}
                  onChange={(e) => {
                    if (!topicsLoading) {
                      setSelectedTopic(e.target.value);
                    }
                  }}
                  className={`flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 bg-bg-primary border-accent/20 text-text-primary ${topicsLoading ? "opacity-50 cursor-not-allowed" : ""}`}
                  disabled={topicsLoading}
                >
                  <option value="">{topicsLoading ? "加载话题中..." : "选择话题"}</option>
                  {topics?.map((topic) => (
                    <option key={topic.id} value={topic.id}>
                      {topic.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-4">
                <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-accent">
                  <Users className="w-3 h-3" />
                  用户选择
                </div>
                <Select
                  value={selectedUserSource}
                  onValueChange={(value) => setSelectedUserSource(value as 'topic-original')}
                >
                  <SelectTrigger className="bg-bg-primary border-accent/20 text-text-primary">
                    <SelectValue placeholder="选择用户来源" value={originalUserSourceLabel} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="topic-original">{originalUserSourceLabel}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-6">
              <div className="space-y-4">
                <div className="flex justify-between items-end">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">Agent 数量</label>
                  <span className="text-xl font-mono font-bold text-accent">{agentCount[0].toLocaleString()}</span>
                </div>
                <Slider
                  value={agentCount}
                  onValueChange={(val) => {
                    setAgentCount(val);
                    // 只更新本地状态，不调用 API
                  }}
                  min={availableOriginalUserCount > 0 ? 1 : 0}
                  max={maxUserCount}
                  step={1}
                  className="py-2"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <Button
                  className={cn("h-12 rounded-lg font-bold gap-2 shadow-lg transition-all active:scale-95",
                    // Use state field if available, otherwise fall back to running/paused
                    ((currentStatus.state === 'running' || currentStatus.running) && currentStatus.state !== 'paused' && !currentStatus.paused) ?
                      "bg-bg-tertiary hover:bg-border-strong text-text-primary" :
                      "bg-accent hover:bg-accent-hover text-bg-primary shadow-accent/20"
                  )}
                  disabled={isStarting}
                  onClick={async () => {
                    try {
                      // Use state field if available
                      const isRunning = currentStatus.state ? currentStatus.state === 'running' : (currentStatus.running && !currentStatus.paused);

                      if (isRunning) {
                        await simulationApi.pause();
                        const statusRes = await simulationApi.getStatus();
                        setStatus(normalizeSimulationStatus(statusRes.data));
                        await refetchStatus();
                        toast.info('仿真已暂停');
                        return;
                      }

                      if (!selectedTopic) {
                        toast.error('请先选择话题');
                        return;
                      }

                      if (!isSupportedSimulationPlatform) {
                        toast.error('当前平台暂无可用仿真数据');
                        return;
                      }

                      if (availableOriginalUserCount <= 0) {
                        toast.error('当前话题没有可用的原始用户');
                        return;
                      }

                      setIsStarting(true);
                      toast.info('正在启动仿真...');

                      const profilesResponse = await simulationApi.getTopicProfiles(selectedTopic, {
                        platform: selectedPlatform,
                        limit: agentCount[0],
                      });
                      const manualProfiles = profilesResponse.data.profiles ?? [];

                      if (manualProfiles.length === 0) {
                        throw new Error('当前话题没有可用的原始用户');
                      }

                      const configResponse = await simulationApi.updateConfig({
                        platform: selectedPlatform,
                        agentCount: manualProfiles.length,
                        maxSteps: 100,
                        recsysType: selectedPlatform,
                        agentSource: {
                          sourceType: 'manual',
                          manualConfig: manualProfiles.map((profile) => profile.agent_config),
                        },
                      });

                      if (configResponse.data?.success === false) {
                        throw new Error(configResponse.data.message || '仿真配置失败');
                      }

                      const activationResponse = await simulationApi.activateTopic(selectedTopic, {
                        platform: selectedPlatform,
                      });

                      if (activationResponse.data?.success === false) {
                        throw new Error(activationResponse.data.message || '话题激活失败');
                      }

                      const stepResponse = await simulationApi.step('auto');
                      const stepResult = stepResponse.data as any;
                      if (stepResult?.success === false) {
                        throw new Error(stepResult.message || '仿真启动失败');
                      }

                      const statusRes = await simulationApi.getStatus();
                      const normalizedStatus = normalizeSimulationStatus(statusRes.data);
                      setStatus(normalizedStatus);
                      await refetchStatus();

                      if (stepResult?.task_id) {
                        toast.success(
                          `仿真已启动: ${selectedTopicMeta?.name || selectedTopic} / 原始用户 ${manualProfiles.length} 人，正在后台执行`,
                        );
                      } else {
                        toast.success(
                          `仿真已启动: ${selectedTopicMeta?.name || selectedTopic} / 原始用户 ${manualProfiles.length} 人 / 当前步数 ${normalizedStatus.currentStep ?? 0}`,
                        );
                      }
                    } catch (e) {
                      console.error('启动/暂停失败:', e);
                      toast.error(`启动失败: ${getRequestErrorMessage(e)}`);
                    } finally {
                      setIsStarting(false);
                    }
                  }}
                >
                  {isStarting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                      启动中...
                    </>
                  ) : (
                    <>
                      {
                        // Use state field if available, otherwise fall back to running/paused
                        (currentStatus.state ?
                          (currentStatus.state === 'running' ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />)
                          :
                          (currentStatus.running && !currentStatus.paused ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />)
                        )
                      }
                      {
                        // Use state field if available, otherwise fall back to running/paused
                        (currentStatus.state ?
                          (currentStatus.state === 'running' ? '暂停' : '启动')
                          :
                          (currentStatus.running && !currentStatus.paused ? '暂停' : '启动')
                        )
                      }
                    </>
                  )}
                </Button>
                <Button
                  variant="secondary"
                  className="h-12 rounded-lg font-bold gap-2 border-accent/30 hover:bg-bg-tertiary transition-all active:scale-95"
                  disabled={isStepping}
                  onClick={async () => {
                    setIsStepping(true);
                    try {
                      await simulationApi.step('auto');
                      const res = await simulationApi.getStatus();
                      setStatus(normalizeSimulationStatus(res.data));
                      await refetchStatus();
                      toast.success('步进完成');
                    } catch (e) {
                      console.error('步进失败:', e);
                      toast.error('步进失败');
                    } finally {
                      setIsStepping(false);
                    }
                  }}
                >
                  <StepForward className={cn("w-4 h-4", isStepping && "animate-spin")} />
                  单步
                </Button>
                <Button
                  variant="secondary"
                  className="h-12 rounded-lg font-bold gap-2 border-rose-500/30 hover:bg-rose-500/10 transition-all active:scale-95"
                  onClick={async () => {
                    try {
                      await simulationApi.reset();
                      // 重新获取状态
                      const statusRes = await simulationApi.getStatus();
                      setStatus(normalizeSimulationStatus(statusRes.data));
                      await refetchStatus();
                      toast.success('仿真已重置');
                    } catch (e) {
                      console.error('重置失败:', e);
                      toast.error('重置失败');
                    }
                  }}
                >
                  <RotateCcw className="w-4 h-4" />
                  重置
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* Combined Chart Section (Situational Awareness) */}
        <div className="lg:col-span-6 space-y-4">
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
                      <Zap className="w-3 h-3" /> 极化计算模型
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
                      <Activity className="w-3 h-3" /> 从众效应评估
                    </h4>
                    <p>利用 Asch 范式数字化模型，监测群体压力影响。</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <SituationalAwarenessChart currentStep={currentStep || 0} />
        </div>
      </div>

      {/* Analytics Merge Section */}
      <div className="pt-12 border-t border-accent/20 space-y-8">
        {/* Loading State for History */}
        {historyLoading && (
          <div className="col-span-full flex items-center justify-center p-12">
            <div className="flex flex-col items-center gap-4">
              <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-text-tertiary">加载历史指标数据中...</p>
            </div>
          </div>
        )}
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
                    <XAxis dataKey="currentStep" stroke="#52525b" fontSize={8} tickLine={false} axisLine={false} />
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
                    <XAxis dataKey="currentStep" stroke="#52525b" fontSize={8} tickLine={false} axisLine={false} />
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
              {opinionDistribution && opinionDistribution.length > 0 ? (
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
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                    <span>加载观点分布数据中...</span>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

