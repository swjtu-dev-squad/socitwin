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

  const distributionData = [
    { name: '极左', value: 15, color: '#f43f5e' },
    { name: '中立', value: 45, color: '#71717a' },
    { name: '极右', value: 40, color: '#3b82f6' },
  ];

  const metrics = [
    { 
      label: '群体极化率', 
      value: `${(status.polarization * 100).toFixed(1)}%`, 
      trend: '+2.4%', 
      up: true,
      icon: Zap,
      color: 'text-rose-500'
    },
    { 
      label: '信息传播速度', 
      value: '142 msg/s', 
      trend: '+12%', 
      up: true,
      icon: TrendingUp,
      color: 'text-emerald-500'
    },
    { 
      label: '从众效应指数', 
      value: '0.64', 
      trend: '-0.05', 
      up: false,
      icon: Users,
      color: 'text-blue-500'
    },
    { 
      label: 'A/B 测试偏差', 
      value: '1.2%', 
      trend: '稳定', 
      up: null,
      icon: Activity,
      color: 'text-zinc-500'
    },
  ];

  return (
    <div className="p-8 h-full flex flex-col space-y-8">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <BarChart3 className="w-10 h-10 text-emerald-500" />
            分析仪表板
          </h1>
          <p className="text-zinc-500 mt-1">深度解析模拟数据，洞察群体行为规律</p>
        </div>
        <div className="flex gap-4">
          <Button variant="outline" className="rounded-xl border-zinc-800 h-10 text-xs gap-2">
            <Share2 className="w-4 h-4" />
            生成报告
          </Button>
          <Link to="/control">
            <Button className="bg-emerald-600 hover:bg-emerald-700 rounded-xl h-10 text-xs font-bold px-6">
              调整模拟参数
            </Button>
          </Link>
        </div>
      </header>

      {history.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center bg-zinc-900/30 rounded-3xl border border-zinc-800 border-dashed">
          <div className="w-32 h-32 bg-zinc-900 rounded-full flex items-center justify-center mb-8 opacity-20">
            <Activity className="w-12 h-12 text-emerald-500" />
          </div>
          <h3 className="text-2xl font-bold text-zinc-400 mb-2">暂无分析数据</h3>
          <p className="text-sm text-zinc-600 max-w-sm mb-8">
            模拟尚未启动或正在初始化中。启动模拟后，系统将实时收集并分析智能体的行为数据，为您呈现多维度的洞察图表。
          </p>
          <Link to="/control">
            <Button className="bg-emerald-600 hover:bg-emerald-700 rounded-xl px-10 h-12 font-bold gap-2">
              <Zap className="w-4 h-4" />
              立即启动模拟
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {metrics.map((m, i) => (
            <Card key={i} className="p-6 bg-zinc-900 border-zinc-800 hover:border-zinc-700 transition-all group">
              <div className="flex justify-between items-start mb-4">
                <div className="p-2 bg-zinc-950 rounded-lg border border-zinc-800 group-hover:border-zinc-700 transition-colors">
                  <m.icon className={cn("w-5 h-5", m.color)} />
                </div>
                {m.up !== null && (
                  <Badge variant="outline" className={cn(
                    "text-[10px] gap-1",
                    m.up ? "text-emerald-500 border-emerald-500/20 bg-emerald-500/5" : "text-rose-500 border-rose-500/20 bg-rose-500/5"
                  )}>
                    {m.up ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {m.trend}
                  </Badge>
                )}
              </div>
              <p className="text-xs font-bold text-zinc-500 uppercase tracking-widest mb-1">{m.label}</p>
              <h3 className="text-3xl font-bold tracking-tighter text-zinc-100">{m.value}</h3>
            </Card>
          ))}

          {/* Polarization Trend */}
          <Card className="md:col-span-2 lg:col-span-3 p-6 bg-zinc-900 border-zinc-800 flex flex-col h-[400px]">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-rose-500" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">群体极化演化趋势</h3>
              </div>
              <div className="flex gap-2">
                <Badge variant="outline" className="bg-rose-500/10 border-rose-500/20 text-rose-500 text-[10px]">实时监控</Badge>
              </div>
            </div>
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={polarizationData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#18181b" vertical={false} />
                  <XAxis 
                    dataKey="time" 
                    stroke="#3f3f46" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false}
                    minTickGap={30}
                  />
                  <YAxis 
                    stroke="#3f3f46" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false} 
                    domain={[0, 1]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '12px' }}
                    itemStyle={{ color: '#f43f5e', fontSize: '12px', fontWeight: 'bold' }}
                    labelStyle={{ color: '#71717a', fontSize: '10px', marginBottom: '4px' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="value" 
                    stroke="#f43f5e" 
                    strokeWidth={3} 
                    dot={false} 
                    activeDot={{ r: 6, strokeWidth: 0, fill: '#f43f5e' }}
                    animationDuration={1000}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Opinion Distribution */}
          <Card className="p-6 bg-zinc-900 border-zinc-800 flex flex-col h-[400px]">
            <div className="flex items-center gap-2 mb-6">
              <PieChartIcon className="w-4 h-4 text-emerald-500" />
              <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">观点分布矩阵</h3>
            </div>
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distributionData} layout="vertical">
                  <XAxis type="number" hide />
                  <YAxis 
                    dataKey="name" 
                    type="category" 
                    stroke="#71717a" 
                    fontSize={10} 
                    tickLine={false} 
                    axisLine={false}
                    width={40}
                  />
                  <Tooltip 
                    cursor={{ fill: 'transparent' }}
                    contentStyle={{ backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '12px' }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={32}>
                    {distributionData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 space-y-2">
              {distributionData.map((d, i) => (
                <div key={i} className="flex justify-between items-center text-[10px]">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: d.color }}></div>
                    <span className="text-zinc-400 font-bold">{d.name}</span>
                  </div>
                  <span className="text-zinc-100 font-mono">{d.value}%</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Propagation Analysis */}
          <Card className="md:col-span-2 p-6 bg-zinc-900 border-zinc-800">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-emerald-500" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">传播节点分析</h3>
              </div>
              <Button variant="ghost" className="h-8 text-[10px] text-zinc-500 hover:text-zinc-300">查看完整拓扑</Button>
            </div>
            <div className="space-y-4">
              {[1, 2, 3].map((_, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-zinc-950 rounded-xl border border-zinc-800/50 hover:border-emerald-500/30 transition-colors cursor-pointer group">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-zinc-900 flex items-center justify-center text-xs font-bold text-zinc-600 group-hover:text-emerald-500 transition-colors">
                      #{i + 1}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-zinc-200">Agent_X{i * 42}</p>
                      <p className="text-[10px] text-zinc-600">影响力指数: 0.9{8-i}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-bold text-emerald-500">关键传播者</p>
                    <p className="text-[9px] text-zinc-700">触达 1.2k 节点</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* A/B Test Results */}
          <Card className="md:col-span-2 p-6 bg-zinc-900 border-zinc-800">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-2">
                <Info className="w-4 h-4 text-blue-500" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-400">A/B 测试对比 (算法干预)</h3>
              </div>
              <Badge variant="outline" className="text-[10px] border-blue-500/20 text-blue-500">进行中</Badge>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-zinc-950 rounded-2xl border border-zinc-800">
                <p className="text-[10px] font-bold text-zinc-600 uppercase mb-2">组 A (对照组)</p>
                <div className="flex items-end gap-2 mb-1">
                  <span className="text-2xl font-bold text-zinc-200">0.42</span>
                  <span className="text-[10px] text-zinc-600 mb-1">极化率</span>
                </div>
                <div className="w-full bg-zinc-900 h-1 rounded-full overflow-hidden">
                  <div className="bg-zinc-600 h-full" style={{ width: '42%' }}></div>
                </div>
              </div>
              <div className="p-4 bg-zinc-950 rounded-2xl border border-emerald-500/20 bg-emerald-500/5">
                <p className="text-[10px] font-bold text-emerald-600 uppercase mb-2">组 B (干预组)</p>
                <div className="flex items-end gap-2 mb-1">
                  <span className="text-2xl font-bold text-emerald-500">0.28</span>
                  <span className="text-[10px] text-emerald-600 mb-1">极化率</span>
                </div>
                <div className="w-full bg-zinc-900 h-1 rounded-full overflow-hidden">
                  <div className="bg-emerald-500 h-full" style={{ width: '28%' }}></div>
                </div>
              </div>
            </div>
            <p className="mt-4 text-[10px] text-zinc-600 leading-relaxed italic">
              * 算法干预组通过调整推荐权重，成功将极化增长率降低了 33.3%。
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
