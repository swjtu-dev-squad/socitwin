import { useMemo } from 'react';
import { useSimulationStore } from '@/lib/store';
import { 
  Card,
  Button,
  Badge
} from '@/components/ui';
import { 
  BarChart3, 
  TrendingUp, 
  Users, 
  Zap, 
  ArrowUpRight, 
  ArrowDownRight,
  Info,
  PieChart as PieChartIcon,
  Activity,
  Share2
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell
} from 'recharts';
import { Link } from 'react-router-dom';

export default function Analytics() {
  const { history, status } = useSimulationStore();

  const polarizationData = useMemo(() => {
    return history.map(h => ({
      time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      value: h.polarization
    }));
  }, [history]);

  // Calculate polarization trend from history data
  const polarizationTrend = useMemo(() => {
    if (history.length < 2) return '0%';
    const prev = history[history.length - 2].polarization;
    const curr = status.polarization;
    const change = ((curr - prev) / (prev || 1)) * 100;
    return `${change > 0 ? '+' : ''}${change.toFixed(1)}%`;
  }, [history, status.polarization]);

  // Calculate information velocity from posts and time
  const informationVelocity = useMemo(() => {
    if (history.length === 0) return { value: '0 msg/s', trend: '0%' };

    // Calculate posts per second from last step
    const lastEntry = history[history.length - 1];
    const prevEntry = history[history.length - 2] || { timestamp: Date.now(), totalPosts: 0 };

    const timeDiff = (lastEntry.timestamp - prevEntry.timestamp) / 1000; // seconds
    const postsDiff = lastEntry.totalPosts - prevEntry.totalPosts;

    if (timeDiff <= 0) return { value: '0 msg/s', trend: '0%' };

    const velocity = Math.round(postsDiff / timeDiff);

    // Calculate trend (compare with previous)
    const prevPrevEntry = history[history.length - 3] || prevEntry;
    const prevTimeDiff = (prevEntry.timestamp - prevPrevEntry.timestamp) / 1000;
    const prevPostsDiff = prevEntry.totalPosts - (prevPrevEntry.totalPosts || 0);
    const prevVelocity = prevTimeDiff > 0 ? prevPostsDiff / prevTimeDiff : 0;

    const trendPercent = prevVelocity > 0
      ? ((velocity - prevVelocity) / prevVelocity) * 100
      : 0;

    return {
      value: `${velocity} msg/s`,
      trend: `${trendPercent > 0 ? '+' : ''}${trendPercent.toFixed(0)}%`,
    };
  }, [history]);

  // Opinion distribution - zeros until agents have ideology attributes
  // TODO: Calculate from agent ideology when available
  // Currently agents don't have ideology/political leaning attributes
  // Leave as zeros until backend adds this data
  const opinionDistribution = useMemo(() => {
    return [
      { name: '极左', value: 0, color: '#f43f5e' },
      { name: '中立', value: 0, color: '#71717a' },
      { name: '极右', value: 0, color: '#3b82f6' },
    ];
  }, []);

  const metrics = [
    {
      label: '群体极化率',
      value: `${(status.polarization * 100).toFixed(1)}%`,
      trend: polarizationTrend,
      up: !polarizationTrend.startsWith('-'),
      icon: Zap,
      color: 'text-rose-500'
    },
    {
      label: '信息传播速度',
      value: informationVelocity.value,
      trend: informationVelocity.trend,
      up: !informationVelocity.trend.startsWith('-'),
      icon: TrendingUp,
      color: 'text-emerald-500'
    },
    {
      label: '从众效应指数',
      value: 'Coming Soon',
      trend: null,
      up: null,
      icon: Users,
      color: 'text-text-muted',
      disabled: true,
    },
    {
      label: 'A/B 测试偏差',
      value: 'Coming Soon',
      trend: null,
      up: null,
      icon: Activity,
      color: 'text-text-muted',
      disabled: true,
    },
  ];

  return (
    <div className="px-6 lg:px-12 xl:px-16 py-12 h-full flex flex-col">
      <div className="max-w-7xl mx-auto space-y-8 flex-1 min-h-0">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <BarChart3 className="w-10 h-10 text-accent" />
            分析仪表板
          </h1>
          <p className="text-text-tertiary mt-1">深度解析模拟数据，洞察群体行为规律</p>
        </div>
        <div className="flex gap-4">
          <Button variant="outline" className="rounded-xl border-border-default h-10 text-xs gap-2">
            <Share2 className="w-4 h-4" />
            生成报告
          </Button>
          <Link to="/control">
            <Button className="bg-accent hover:bg-accent-hover rounded-xl h-10 text-xs font-bold px-6">
              调整模拟参数
            </Button>
          </Link>
        </div>
      </header>

      {history.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-bg-secondary/30 rounded-3xl border border-border-default border-dashed">
          <div className="w-32 h-32 bg-bg-secondary rounded-full flex items-center justify-center mb-8 opacity-20">
            <Activity className="w-12 h-12 text-accent" />
          </div>
          <h3 className="text-2xl font-bold text-text-secondary mb-2">暂无分析数据</h3>
          <p className="text-sm text-text-muted max-w-sm mb-8">
            模拟尚未启动或正在初始化中。启动模拟后，系统将实时收集并分析智能体的行为数据，为您呈现多维度的洞察图表。
          </p>
          <Link to="/control">
            <Button className="bg-accent hover:bg-accent-hover rounded-xl px-10 h-12 font-bold gap-2">
              <Zap className="w-4 h-4" />
              立即启动模拟
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {metrics.map((m, i) => (
            <Card
              key={i}
              className={cn(
                "p-6 bg-bg-secondary border-border-default transition-all group",
                m.disabled ? "opacity-50" : "hover:border-border-strong"
              )}
            >
              <div className="flex justify-between items-start mb-4">
                <div className={cn(
                  "p-2 rounded-lg border transition-colors",
                  m.disabled ? "bg-bg-primary border-border-default" : "bg-bg-primary border-border-default group-hover:border-border-strong"
                )}>
                  <m.icon className={cn("w-5 h-5", m.color)} />
                </div>
                {!m.disabled && m.up !== null && (
                  <Badge variant="outline" className={cn(
                    "text-[10px] gap-1",
                    m.up ? "text-emerald-500 border-emerald-500/20 bg-emerald-500/5" : "text-rose-500 border-rose-500/20 bg-rose-500/5"
                  )}>
                    {m.up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {m.trend}
                  </Badge>
                )}
              </div>
              <p className="text-xs font-bold text-text-tertiary uppercase tracking-widest mb-1">{m.label}</p>
              <h3 className={cn(
                "text-3xl font-bold tracking-tighter",
                m.disabled ? "text-text-muted" : "text-text-primary"
              )}>{m.value}</h3>
            </Card>
          ))}

          {/* Polarization Trend */}
          <Card className="md:col-span-2 lg:col-span-3 p-6 bg-bg-secondary border-border-default flex flex-col h-[400px]">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-rose-500" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-text-secondary">群体极化演化趋势</h3>
              </div>
              <div className="flex gap-2">
                <Badge variant="outline" className="bg-rose-500/10 border-rose-500/20 text-rose-500 text-[10px]">实时监控</Badge>
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={polarizationData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#24201E" vertical={false} />
                  <XAxis
                    dataKey="time"
                    stroke="#1A1614"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={30}
                  />
                  <YAxis
                    stroke="#1A1614"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    domain={[0, 1]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0D0D0D', border: '1px solid #24201E', borderRadius: '12px' }}
                    itemStyle={{ color: '#D72638', fontSize: '12px', fontWeight: 'bold' }}
                    labelStyle={{ color: '#1A1A1A', fontSize: '10px', marginBottom: '4px' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#D72638"
                    strokeWidth={3}
                    dot={false}
                    activeDot={{ r: 6, strokeWidth: 0, fill: '#D72638' }}
                    animationDuration={1000}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Opinion Distribution */}
          <Card className="p-6 bg-bg-secondary border-border-default flex flex-col h-[400px]">
            <div className="flex items-center gap-2 mb-6">
              <PieChartIcon className="w-4 h-4 text-accent" />
              <h3 className="text-sm font-bold uppercase tracking-widest text-text-secondary">观点分布矩阵</h3>
            </div>
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={opinionDistribution} layout="vertical">
                  <XAxis type="number" hide />
                  <YAxis
                    dataKey="name"
                    type="category"
                    stroke="#1A1A1A"
                    fontSize={10}
                    tickLine={false}
                    axisLine={false}
                    width={40}
                  />
                  <Tooltip
                    cursor={{ fill: 'transparent' }}
                    contentStyle={{ backgroundColor: '#0D0D0D', border: '1px solid #24201E', borderRadius: '12px' }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={32}>
                    {opinionDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 space-y-2">
              {opinionDistribution.map((d, i) => (
                <div key={i} className="flex justify-between items-center text-[10px]">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }}></div>
                    <span className="text-text-secondary font-bold">{d.name}</span>
                  </div>
                  <span className="text-text-primary font-mono">{d.value}%</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Propagation Analysis */}
          <Card className="md:col-span-2 p-6 bg-bg-secondary border-border-default">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-text-secondary">传播节点分析</h3>
              </div>
            </div>
            <div className="flex items-center justify-center h-48 text-text-tertiary">
              <div className="text-center">
                <Zap className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">传播节点分析</p>
                <p className="text-xs mt-1 opacity-70">Coming Soon</p>
                <p className="text-[9px] mt-2 text-text-muted max-w-xs mx-auto">
                  需要后端实现社交网络分析算法
                </p>
              </div>
            </div>
          </Card>

          {/* A/B Test Results */}
          <Card className="md:col-span-2 p-6 bg-bg-secondary border-border-default">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-blue-500" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-text-secondary">A/B 测试对比 (算法干预)</h3>
              </div>
            </div>
            <div className="flex items-center justify-center h-48 text-text-tertiary">
              <div className="text-center">
                <Activity className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">A/B 测试对比</p>
                <p className="text-xs mt-1 opacity-70">Coming Soon</p>
                <p className="text-[9px] mt-2 text-text-muted max-w-xs mx-auto">
                  需要后端实现分组测试基础设施
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}
      </div>
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
