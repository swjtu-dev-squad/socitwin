import { useEffect } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Button, Badge } from '@/components/ui';
import { Link, useNavigate } from 'react-router-dom';
import { simulationApi } from '@/lib/api';
import { 
  Users, 
  FileText, 
  Activity, 
  Zap, 
  TrendingUp, 
  AlertTriangle,
  RefreshCw,
  ArrowRight,
  Play,
  UserPlus,
  BarChart3,
  Globe,
  Cpu
} from 'lucide-react';
import { 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';

export default function Overview() {
  const { status, history, setStatus } = useSimulationStore();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await simulationApi.getStatus();
        setStatus(res.data);
      } catch (error) {
        console.error('Failed to fetch simulation status:', error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 1500); // 1.5s refresh
    return () => clearInterval(interval);
  }, [setStatus]);

  const stats = [
    { name: '活跃 Agent', value: status.activeAgents.toLocaleString(), change: '+2.3%', icon: Users, color: 'text-accent', path: '/agents' },
    { name: '总帖子数', value: status.totalPosts.toLocaleString(), change: '+1.8%', icon: FileText, color: 'text-blue-400', path: '/logs' },
    { name: '当前步数', value: status.currentStep.toLocaleString(), change: '', icon: Zap, color: 'text-yellow-400', path: '/control' },
    { name: '极化指数', value: status.polarization.toFixed(2), change: status.polarization > 0.7 ? '高风险' : '正常', icon: Activity, color: 'text-rose-400', path: '/analytics' },
  ];

  const chartData = history.length > 0 ? history : Array.from({ length: 20 }, (_, i) => ({
    currentStep: i,
    polarization: 0,
    totalPosts: 0,
  }));

  return (
    <div className="p-8 space-y-8">
      <header className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-4xl font-bold tracking-tight">系统概览</h1>
              <div className={cn(
                "flex items-center gap-2 px-3 py-1 rounded-full border text-[10px] font-bold uppercase tracking-widest",
                status.running && !status.paused ? "bg-accent-subtle border-accent/20 text-accent" :
                status.paused ? "bg-amber-500/10 border-amber-500/20 text-amber-500" : "bg-bg-tertiary border-border-default text-text-tertiary"
              )}>
                <div className={cn("w-1.5 h-1.5 rounded-full",
                  status.running && !status.paused ? "bg-accent animate-pulse" :
                  status.paused ? "bg-amber-500" : "bg-text-muted"
                )}></div>
                {status.running && !status.paused ? 'Running' : status.paused ? 'Paused' : 'Stopped'}
              </div>
              {status.platform && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-7 px-3 rounded-full">
                  <Globe className="w-3 h-3 text-orange-500" />
                  {status.platform}
                </Badge>
              )}
              {status.recsys && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-7 px-3 rounded-full">
                  <Cpu className="w-3 h-3 text-blue-500" />
                  RecSys: {status.recsys}
                </Badge>
              )}
              {status.regions && status.regions.length > 0 && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-7 px-3 rounded-full">
                  <Globe className="w-3 h-3 text-purple-500" />
                  {status.regions.join(', ')}
                </Badge>
              )}
              {status.topics && status.topics.length > 0 && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-7 px-3 rounded-full">
                  <Zap className="w-3 h-3 text-yellow-500" />
                  {status.topics.length} Topics
                </Badge>
              )}
            </div>
            <p className="text-text-tertiary mt-1">实时监控 OASIS 模拟引擎运行状态</p>
          </div>
        </div>
        <Button
          variant="outline"
          className="rounded-xl border-border-default gap-2 text-xs h-10"
          onClick={async () => {
            const res = await simulationApi.getStatus();
            setStatus(res.data);
          }}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          刷新全部
        </Button>
      </header>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat) => {
          const isZero = stat.value === "0" || stat.value === "0.00";
          return (
            <Card
              key={stat.name}
              className="bg-bg-secondary border-border-default p-6 hover:border-accent/50 transition-all group relative overflow-hidden cursor-pointer"
              onClick={() => navigate(stat.path)}
            >
              <div className="absolute top-0 right-0 p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <ArrowRight className="w-4 h-4 text-text-tertiary" />
              </div>
              <div className="flex justify-between items-start">
                <div className={cn("p-2 rounded-lg bg-bg-tertiary", stat.color)}>
                  <stat.icon className="w-5 h-5" />
                </div>
                {stat.change && !isZero && (
                  <span className={cn("text-[10px] font-bold px-2 py-1 rounded-full bg-bg-tertiary",
                    stat.change.includes('+') ? "text-emerald-400" : "text-rose-400"
                  )}>
                    {stat.change}
                  </span>
                )}
              </div>
              <div className="mt-4">
                <p className="text-sm text-text-tertiary font-medium">{stat.name}</p>
                {isZero ? (
                  <div className="space-y-3 mt-1">
                    <h3 className="text-xl font-bold text-text-muted font-mono tracking-tight italic">模拟未启动</h3>
                    <Button
                      variant="outline"
                      className="w-full h-8 text-[10px] border-accent/30 text-accent hover:bg-accent-subtle rounded-lg gap-1"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate('/control');
                      }}
                    >
                      去控制中心启动 <ArrowRight className="w-3 h-3" />
                    </Button>
                  </div>
                ) : (
                  <h3 className="text-2xl font-bold mt-1 font-mono tracking-tight">{stat.value}</h3>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart */}
        <Card className="lg:col-span-2 bg-bg-secondary border-border-default p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-accent" />
              实时趋势分析
            </h2>
            <div className="flex gap-4 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-accent"></div>
                <span className="text-text-secondary">极化指数</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span className="text-text-secondary">传播深度</span>
              </div>
            </div>
          </div>
          <div className="h-[300px] w-full relative">
            {history.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-bg-primary/20 rounded-xl border border-dashed border-border-default">
                <div className="w-16 h-16 bg-bg-secondary rounded-full flex items-center justify-center mb-4 opacity-20">
                  <TrendingUp className="w-8 h-8 text-accent" />
                </div>
                <p className="text-sm text-text-tertiary font-medium">启动模拟后将显示实时趋势</p>
                <p className="text-[10px] text-text-muted mt-1 uppercase tracking-widest font-bold">OASIS ENGINE v1.0</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorPol" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#D72638" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="#F46036" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#24201E" vertical={false} />
                  <XAxis dataKey="currentStep" stroke="#1A1614" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#1A1614" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1A1614', border: '1px solid #24201E', borderRadius: '8px' }}
                    itemStyle={{ fontSize: '12px' }}
                  />
                  <Area type="monotone" dataKey="polarization" stroke="#D72638" fillOpacity={1} fill="url(#colorPol)" strokeWidth={2} />
                  <Area type="monotone" dataKey="totalPosts" stroke="#3b82f6" fillOpacity={0} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>

        {/* Alerts / Phenomena */}
        <Card className="bg-bg-secondary border-border-default p-6">
          <h2 className="text-lg font-bold mb-6 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            异常现象警报
          </h2>
          <div className="space-y-4">
            {[
              { title: '群体极化加速', desc: 'Reddit 平台极化指数在过去 10 步内上升 15%', level: 'High' },
              { title: '谣言传播链', desc: '检测到深度为 12 的信息传播树', level: 'Medium' },
              { title: '从众效应显著', desc: 'Agent 决策一致性超过 85%', level: 'Low' },
            ].map((alert) => (
              <div key={alert.title} className="p-4 rounded-xl bg-bg-tertiary/50 border border-border-default hover:border-border-strong transition-colors group/alert">
                <div className="flex justify-between items-start mb-1">
                  <h4 className="text-sm font-bold text-text-primary">{alert.title}</h4>
                  <span className={cn("text-[10px] px-2 py-0.5 rounded-full font-bold uppercase", 
                    alert.level === 'High' ? "bg-rose-500/20 text-rose-400" : 
                    alert.level === 'Medium' ? "bg-yellow-500/20 text-yellow-400" : "bg-blue-500/20 text-blue-400"
                  )}>
                    {alert.level}
                  </span>
                </div>
                <p className="text-xs text-text-tertiary leading-relaxed">{alert.desc}</p>
                <div className="mt-3 opacity-0 group-hover/alert:opacity-100 transition-opacity">
                  <Button
                    variant="outline"
                    className="w-full h-7 text-[10px] border-border-default hover:bg-bg-tertiary rounded-lg gap-1"
                    onClick={() => navigate('/analytics')}
                  >
                    查看详情 <ArrowRight className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Quick Start Bar */}
      <Card className="p-4 bg-accent-subtle border-accent/20 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 rounded-xl bg-accent-subtle flex items-center justify-center">
            <Zap className="w-5 h-5 text-accent" />
          </div>
          <div>
            <p className="text-sm font-bold text-accent">快速开始引导</p>
            <p className="text-xs text-text-tertiary">按照以下步骤快速启动您的社交模拟实验</p>
          </div>
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            className="h-10 rounded-xl border-border-default text-xs gap-2"
            onClick={() => navigate('/control')}
          >
            <Play className="w-4 h-4" />
            1. 配置引擎
          </Button>
          <Button
            variant="outline"
            className="h-10 rounded-xl border-border-default text-xs gap-2"
            onClick={() => navigate('/profiles')}
          >
            <UserPlus className="w-4 h-4" />
            2. 生成画像
          </Button>
          <Button
            className="h-10 rounded-xl bg-accent hover:bg-accent-hover text-xs gap-2"
            onClick={() => navigate('/agents')}
          >
            <BarChart3 className="w-4 h-4" />
            3. 监控网络
          </Button>
        </div>
      </Card>
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
