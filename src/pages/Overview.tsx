import { useEffect, useState } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Button, Badge, Slider, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui';
import { useNavigate } from 'react-router-dom';
import { simulationApi } from '@/lib/api';
import {
  Users,
  FileText,
  Activity,
  Zap,
  TrendingUp,
  AlertTriangle,
  Globe,
  Cpu,
  Eye,
  Play,
  Pause,
  StepForward,
  RotateCcw,
  Square,
  Settings2
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
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export default function Overview() {
  const { status, history, setStatus } = useSimulationStore();
  const navigate = useNavigate();
  const [agentCount, setAgentCount] = useState([10]); // 默认10个agents
  const [platform, setPlatform] = useState('REDDIT');
  const [recsys, setRecsys] = useState('HOT');
  const [topic, setTopic] = useState('POLITICS');
  const [region, setRegion] = useState('THAILAND');

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await simulationApi.getStatus();
        setStatus(res.data);

        // Sync current running config to state ONLY when simulation is running
        // This prevents overwriting user's manual changes when simulation is not running
        if (res.data.running) {
          if (res.data.platform) setPlatform(res.data.platform);
          if (res.data.recsys) setRecsys(res.data.recsys);
          if (res.data.topics && res.data.topics.length > 0) setTopic(res.data.topics[0]);
          if (res.data.regions && res.data.regions.length > 0) setRegion(res.data.regions[0]);
        }
      } catch (error) {
        console.error('Failed to fetch simulation status:', error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 1500);
    return () => clearInterval(interval);
  }, [setStatus]);

  const stats = [
    {
      label: '活跃 Agents',
      value: status.activeAgents.toLocaleString(),
      icon: Users,
      status: 'healthy',
      path: '/agents'
    },
    {
      label: '总帖子数',
      value: status.totalPosts.toLocaleString(),
      icon: FileText,
      status: 'healthy',
      path: '/logs'
    },
    {
      label: '当前步数',
      value: status.currentStep.toLocaleString(),
      icon: Zap,
      status: 'healthy',
      path: '/overview'
    },
    {
      label: '极化指数',
      value: status.polarization.toFixed(2),
      icon: Activity,
      status: status.polarization > 0.7 ? 'warning' : 'healthy',
      path: '/analytics'
    },
  ];

  // Check if all stats are zero/N/A
  const allStatsZero = stats.every(stat => stat.value === "0" || stat.value === "0.00");

  const chartData = history.length > 0 ? history : Array.from({ length: 20 }, (_, i) => ({
    currentStep: i,
    polarization: 0,
    totalPosts: 0,
  }));

  return (
    <div className="px-6 lg:px-12 xl:px-16 py-12">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex justify-between items-center">
          <div>
            <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
              <Eye className="w-10 h-10 text-accent" />
              概览
            </h1>
            <p className="text-text-tertiary mt-1">实时监控系统运行状态与关键指标</p>
          </div>
          <div className="flex items-center gap-4">
            <div className={cn(
              "h-8 flex items-center gap-2 px-3 rounded-full border text-xs",
              status.running && !status.paused ? "bg-accent-subtle border-accent/20 text-accent" :
              status.paused ? "bg-bg-tertiary border-border-default text-text-secondary" : "bg-bg-tertiary border-border-default text-text-tertiary"
            )}>
              <div className={cn("w-1.5 h-1.5 rounded-full",
                status.running && !status.paused ? "bg-accent" :
                status.paused ? "bg-text-secondary" : "bg-text-muted"
              )}></div>
              {status.running && !status.paused ? '运行中' : status.paused ? '已暂停' : '已停止'}
            </div>
            {/* 所有Badge（在同一行） */}
            <div className="flex items-center gap-3 flex-wrap">
              {status.running && status.platform && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-8 px-3 rounded-full">
                  <Globe className="w-3 h-3 text-text-tertiary" />
                  {status.platform}
                </Badge>
              )}
              {status.running && status.recsys && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-8 px-3 rounded-full">
                  <Cpu className="w-3 h-3 text-text-tertiary" />
                  RecSys: {status.recsys}
                </Badge>
              )}
              {status.running && status.regions && status.regions.length > 0 && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-8 px-3 rounded-full">
                  <Globe className="w-3 h-3 text-text-tertiary" />
                  {status.regions.join(', ')}
                </Badge>
              )}
              {status.running && status.topics && status.topics.length > 0 && (
                <Badge variant="outline" className="bg-bg-secondary border-border-default text-text-secondary gap-1.5 h-8 px-3 rounded-full">
                  <Zap className="w-3 h-3 text-text-tertiary" />
                  {status.topics.length} Topics
                </Badge>
              )}
            </div>
            <Button
              variant="outline"
              className="h-8 px-4 rounded-lg border-border-default text-xs hover:bg-bg-tertiary shrink-0 shadow-none"
              onClick={async () => {
                const res = await simulationApi.getStatus();
                setStatus(res.data);
              }}
            >
              刷新
            </Button>
          </div>
        </header>

        {/* Stats Table and Control - 12 Column Grid */}
        <div className="grid grid-cols-12 gap-6">
          {/* Stats Table - 5 Columns */}
          <Card className="col-span-12 lg:col-span-5 bg-bg-secondary border-border-default p-6 rounded-xl">
            <Table>
              <TableHeader>
                <TableRow className="border-border-default hover:bg-transparent">
                  <TableHead className="text-text-tertiary font-bold text-xs uppercase tracking-widest py-3">指标</TableHead>
                  <TableHead className="text-text-tertiary font-bold text-xs uppercase tracking-widest py-3 text-right">数值</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stats.map((stat) => {
                  const isZero = stat.value === "0" || stat.value === "0.00";
                  return (
                    <TableRow
                      key={stat.label}
                      className="border-border-default hover:bg-bg-tertiary/50 transition-colors cursor-pointer group"
                      onClick={() => navigate(stat.path)}
                    >
                      <TableCell className="py-4">
                        <div className="flex items-center gap-3">
                          <div className="p-2 shrink-0 group-hover:bg-bg-tertiary rounded-lg transition-colors">
                            <stat.icon className="w-4 h-4 text-text-primary" strokeWidth={1.5} />
                          </div>
                          <span className="text-sm text-text-secondary font-medium">{stat.label}</span>
                        </div>
                      </TableCell>
                      <TableCell className="py-4 text-right">
                        {isZero ? (
                          <span className="text-xl text-text-muted tracking-tight font-medium">N/A</span>
                        ) : (
                          <span className="text-xl text-text-primary tracking-tight font-medium">
                            {stat.value}
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>

          {/* Configuration and Control - 7 Columns */}
          <Card className="col-span-12 lg:col-span-7 bg-bg-secondary border-border-default p-6 rounded-xl">
            <div className="flex justify-between items-center border-b border-border-default pb-3 mb-6">
              <h2 className="text-lg flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-accent" />
                参数配置与执行控制
              </h2>
            </div>

            {/* Configuration Display: 2x2 Grid */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">平台</label>
                <Select value={platform} onValueChange={setPlatform}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-11 rounded-xl">
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
                  <SelectTrigger className="bg-bg-primary border-border-default h-11 rounded-xl">
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
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">话题</label>
                <Select value={topic} onValueChange={setTopic}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-11 rounded-xl">
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
                  <SelectTrigger className="bg-bg-primary border-border-default h-11 rounded-xl">
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

            {/* Agent Count Slider */}
            <div className="space-y-2 mb-6">
              <div className="flex justify-between items-center">
                <label className="text-xs uppercase tracking-wider text-text-tertiary">Agent 数量</label>
                <span className="text-sm text-accent font-medium">{agentCount[0].toLocaleString()}</span>
              </div>
              <Slider
                value={agentCount}
                onValueChange={setAgentCount}
                min={10}
                max={100000}
                step={10}
                className="py-2"
              />
            </div>

            {/* Execution Control Buttons: 2x2 Grid */}
            <div className="grid grid-cols-2 gap-3">
              {/* 启动/暂停/恢复按钮 */}
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
                    try {
                      await simulationApi.updateConfig({
                        platform,
                        recsys,
                        agentCount: agentCount[0],
                        topics: [topic],
                        regions: [region],
                      });
                      const statusRes = await simulationApi.getStatus();
                      setStatus(statusRes.data);
                      toast.success("模拟已启动");
                    } catch (error) {
                      toast.error("启动失败");
                    }
                  }
                }}
                variant={status.running && !status.paused ? "secondary" : "default"}
                className="h-12 rounded-xl items-center justify-center gap-2"
              >
                <div className="w-6 h-6 rounded-full flex items-center justify-center shrink-0">
                  {status.running && !status.paused
                    ? <Pause className="w-3 h-3 fill-current" />
                    : <Play className="w-3 h-3 fill-current" />
                  }
                </div>
                <span className="font-medium">{status.running && !status.paused ? '暂停' : status.paused ? '恢复' : '启动模拟'}</span>
              </Button>

              {/* 单步执行按钮 */}
              <Button
                onClick={async () => {
                  try {
                    await simulationApi.step();
                    toast.success("单步执行完成");
                  } catch (error) {
                    toast.error("步进执行失败");
                  }
                }}
                disabled={!status.running && !status.paused}
                variant="secondary"
                className="h-12 rounded-xl items-center justify-center gap-2"
              >
                <StepForward className="w-4 h-4" />
                <span className="font-medium">单步执行</span>
              </Button>

              {/* 重置按钮 */}
              <Button
                onClick={async () => {
                  if (confirm('确定要重置环境吗？所有当前进度将丢失。')) {
                    try {
                      await simulationApi.reset();
                      toast.warning("环境已重置");
                    } catch (error) {
                      toast.error("重置失败");
                    }
                  }
                }}
                variant="outline"
                className="h-12 rounded-xl items-center justify-center gap-2"
              >
                <RotateCcw className="w-4 h-4" />
                <span className="font-medium">重置环境</span>
              </Button>

              {/* 终止按钮 */}
              <Button
                variant="destructive"
                className="h-12 rounded-xl items-center justify-center gap-2"
                onClick={() => {
                  if (confirm('确定要终止模拟并导出数据吗？')) {
                    toast.success("模拟已终止，数据导出中...");
                  }
                }}
              >
                <Square className="w-4 h-4" />
                <span className="font-medium">终止模拟</span>
              </Button>
            </div>
          </Card>
        </div>

        {/* Chart and Alerts Area - Next Row */}
        {allStatsZero ? (
          /* Empty State Guide */
          <div className="flex items-center justify-center py-12">
            <div className="text-center py-12">
              <p className="text-text-secondary text-sm mb-4">模拟未启动，请配置参数后启动</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-12 gap-6">
            {/* Main Chart - 9 Columns */}
            <Card className="col-span-12 lg:col-span-9 bg-bg-secondary border-border-default p-6 rounded-xl">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-accent" />
                  极化趋势
                </h2>
                <div className="flex gap-4 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-accent"></div>
                    <span className="text-text-secondary">极化</span>
                  </div>
                </div>
              </div>
              <div className="h-[320px] w-full relative">
                {history.length === 0 ? (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-bg-primary/20 rounded-xl border border-dashed border-border-default">
                    <div className="w-16 h-16 bg-bg-secondary rounded-full flex items-center justify-center mb-4 opacity-20">
                      <TrendingUp className="w-8 h-8 text-accent" />
                    </div>
                    <p className="text-sm text-text-tertiary font-medium">启动后显示趋势</p>
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
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>

            {/* Alerts - 3 Columns */}
            <Card className="col-span-12 lg:col-span-3 bg-bg-secondary border-border-default p-5 rounded-xl">
              <h3 className="text-base font-medium flex items-center gap-2 mb-4">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                警报
              </h3>

              {!status.running ? (
                <div className="text-center py-6">
                  <div className="w-10 h-10 mx-auto mb-3 rounded-full bg-bg-primary flex items-center justify-center border border-dashed border-border-default">
                    <AlertTriangle className="w-5 h-5 text-text-muted" />
                  </div>
                  <p className="text-sm text-text-muted">无活动警报</p>
                  <p className="text-xs text-text-tertiary mt-1">模拟未启动</p>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-text-muted text-sm">N/A</p>
                </div>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
