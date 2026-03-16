import { useState } from 'react';
import { Card, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Slider, Input, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Badge } from '@/components/ui';
import { UserRound, Sparkles, Download, Database, PlayCircle, ArrowRight, Globe, CheckCircle2 } from 'lucide-react';
import { simulationApi } from '@/lib/api';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export default function Profiles() {
  const navigate = useNavigate();
  const [platform, setPlatform] = useState<'REDDIT' | 'X' | 'FACEBOOK' | 'TIKTOK' | 'INSTAGRAM'>('REDDIT');
  const [count, setCount] = useState([1000]);
  const [seed, setSeed] = useState(42);
  const [agents, setAgents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [topic, setTopic] = useState('POLITICS');
  const [region, setRegion] = useState('THAILAND');
  const [intervalId, setIntervalId] = useState<NodeJS.Timeout | null>(null);

  const generateProfiles = async () => {
    setLoading(true);
    setProgress(0);
    
    // Simulate progress
    const interval = setInterval(() => {
      setProgress(prev => Math.min(prev + Math.random() * 15, 95));
    }, 500);
    setIntervalId(interval);

    try {
      const res = await simulationApi.generateUsers({
        platform,
        count: count[0],
        seed,
        topics: [topic],
        regions: [region],
      });
      setAgents(res.data.agents);
      setProgress(100);
      toast.success(`成功生成 ${res.data.total_generated} 个 ${platform} 智能体画像`, {
        description: `画像已就绪，地区: ${region}`,
        action: {
          label: "前往控制中心",
          onClick: () => navigate('/overview')
        }
      });
    } catch (e) {
      toast.error('画像生成失败，请重试');
      console.error('Generation failed', e);
    } finally {
      clearInterval(interval);
      setIntervalId(null);
      setTimeout(() => setLoading(false), 500);
    }
  };

  const cancelGeneration = () => {
    if (intervalId) {
      clearInterval(intervalId);
      setIntervalId(null);
    }
    setLoading(false);
    setProgress(0);
    toast.info('已取消生成');
  };

  const getPlatformLabel = (p: string) => {
    switch(p) {
      case 'REDDIT': return 'Reddit 社区数据集';
      case 'X': return 'X / Twitter 数据集';
      case 'FACEBOOK': return 'Facebook 关系网络';
      case 'TIKTOK': return 'TikTok 兴趣流';
      case 'INSTAGRAM': return 'Instagram 视觉流';
      default: return p;
    }
  };

  return (
    <div className="px-6 lg:px-12 xl:px-16 py-12">
      <div className="max-w-7xl mx-auto space-y-8">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <UserRound className="w-10 h-10 text-accent" />
            用户画像生成
          </h1>
          <p className="text-text-tertiary mt-1">基于真实数据源扩展生成百万级智能体画像</p>
        </div>
        <div className="flex gap-3">
          {agents.length > 0 && (
            <Button 
              className="bg-accent hover:bg-accent-hover rounded-xl h-10 text-xs font-bold px-6 gap-2 animate-in fade-in slide-in-from-right-4"
              onClick={() => navigate('/overview', { state: { platform, topic, region, agentCount: count[0] } })}
            >
              <PlayCircle className="w-4 h-4" />
              应用并启动模拟
            </Button>
          )}
          <Button variant="outline" className="rounded-xl border-border-default h-10 text-xs font-bold uppercase tracking-widest">
            <Database className="w-3.5 h-3.5 mr-2" />
            从 HF 加载
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Config Panel */}
        <Card className="lg:col-span-4 bg-bg-secondary border-border-default p-8 space-y-8 h-fit">
          <h2 className="text-xl font-bold border-b border-border-default pb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-yellow-400" />
            生成配置
          </h2>
          
          <div className="space-y-8">
            <div className="space-y-2">
              <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">数据源平台</label>
              <Select value={platform} onValueChange={(v: any) => setPlatform(v)}>
                <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                  <SelectValue placeholder="选择数据源" />
                  <span className="text-text-secondary">{getPlatformLabel(platform)}</span>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="REDDIT">Reddit (reddit_user_data_36.json)</SelectItem>
                  <SelectItem value="X">X / Twitter (twitter_user_data_50.json)</SelectItem>
                  <SelectItem value="FACEBOOK">Facebook (fb_social_graph.json)</SelectItem>
                  <SelectItem value="TIKTOK">TikTok (tiktok_interest_v2.json)</SelectItem>
                  <SelectItem value="INSTAGRAM">Instagram (insta_visual_v1.json)</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-[10px] text-text-muted italic">从真实用户特征种子扩展至大规模群体</p>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">Topic 标签</label>
                <Select value={topic} onValueChange={setTopic}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                    <SelectValue placeholder="选择Topic" />
                    <span className="text-text-secondary">{topic}</span>
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
                    <SelectValue placeholder="选择地区" />
                    <span className="text-text-secondary">{region}</span>
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
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">生成数量</label>
                <div className="text-right">
                  <span className="text-3xl font-bold text-accent font-mono tracking-tighter">{count[0].toLocaleString()}</span>
                  <p className="text-[10px] text-text-muted font-bold uppercase">Agents</p>
                </div>
              </div>
              <Slider 
                value={count} 
                onValueChange={setCount} 
                min={100} 
                max={100000} 
                step={100}
                className="py-4"
              />
              <div className="flex justify-between text-[10px] text-text-muted font-bold uppercase tracking-tighter">
                <span>100</span>
                <span>1,000,000 (百万级支持)</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-xs font-bold uppercase tracking-wider text-text-tertiary">随机种子 (Seed)</label>
                <Button variant="outline" className="h-6 px-2 text-[8px] border-border-default rounded-md" onClick={() => setSeed(Math.floor(Math.random() * 1000))}>随机生成</Button>
              </div>
              <Input 
                type="number" 
                value={seed} 
                onChange={(e) => setSeed(parseInt(e.target.value))}
                className="bg-bg-primary border-border-default h-12 rounded-xl font-mono"
              />
            </div>

            <div className="space-y-4">
              {loading ? (
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-text-secondary">
                    <span>生成进度</span>
                    <span className="font-mono">{progress.toFixed(0)}%</span>
                  </div>
                  <div className="h-2 bg-bg-tertiary rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-accent transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="flex justify-between items-center pt-2">
                    <span className="text-[10px] text-text-tertiary">
                      预计剩余时间: {Math.max(1, Math.floor((100 - progress) / 10))} 秒
                    </span>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={cancelGeneration}
                      className="h-6 text-[10px] text-rose-500 hover:text-rose-400 hover:bg-rose-500/10"
                    >
                      取消生成
                    </Button>
                  </div>
                </div>
              ) : (
                <Button 
                  onClick={generateProfiles} 
                  disabled={loading}
                  className="w-full h-16 text-lg font-black bg-accent hover:bg-accent-hover rounded-2xl shadow-xl shadow-accent-glow flex items-center justify-center gap-2 group transition-all active:scale-95"
                >
                  <Sparkles className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  🚀 开始生成画像
                </Button>
              )}
              
              {agents.length > 0 && !loading && (
                <Button 
                  onClick={() => navigate('/overview', { state: { platform, topic, region, agentCount: count[0] } })} 
                  className="w-full h-12 bg-accent hover:bg-accent-hover rounded-2xl font-bold animate-in fade-in slide-in-from-bottom-4"
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  生成完成 → 立即用于当前模拟并启动
                </Button>
              )}
            </div>


            <div className="grid grid-cols-2 gap-4 pt-4">
              <Card 
                className="bg-bg-primary border-border-default p-4 hover:border-accent/30 transition-colors cursor-pointer group flex flex-col items-center gap-2"
                onClick={() => toast.info("正在准备 HF 格式导出...")}
              >
                <Download className="w-5 h-5 text-accent group-hover:scale-110 transition-transform" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-text-secondary">导出 HF 格式</span>
              </Card>
              <Card 
                className="bg-bg-primary border-border-default p-4 hover:border-blue-500/30 transition-colors cursor-pointer group flex flex-col items-center gap-2"
                onClick={() => toast.success("已保存为自定义数据源")}
              >
                <Database className="w-5 h-5 text-blue-400 group-hover:scale-110 transition-transform" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-text-secondary">保存为数据源</span>
              </Card>
            </div>
          </div>
        </Card>

        {/* Preview Table */}
        <Card className="lg:col-span-8 bg-bg-secondary border-border-default flex flex-col overflow-hidden min-h-[600px]">
          <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary">生成结果预览 ({agents.length})</h2>
              {agents.length > 0 && <Badge variant="default" className="bg-accent/20 text-accent border-accent/30 h-5 text-[9px]">已就绪</Badge>}
            </div>
            {agents.length > 0 && (
              <Button 
                variant="ghost" 
                className="h-8 text-[10px] text-text-tertiary hover:text-accent gap-1"
                onClick={() => navigate('/overview')}
              >
                前往控制中心 <ArrowRight className="w-3 h-3" />
              </Button>
            )}
          </div>
          <div className="flex-1 overflow-auto relative">
            {agents.length === 0 ? (
              <div className="absolute inset-0 flex flex-col items-center justify-center p-12 text-center">
                <div className="w-40 h-40 bg-bg-primary rounded-full flex items-center justify-center mb-8 relative">
                  <div className="absolute inset-0 bg-accent-subtle animate-pulse rounded-full"></div>
                  <div className="absolute inset-4 bg-accent/5 rounded-full"></div>
                  <UserRound className="w-20 h-20 text-accent/50" />
                  <Sparkles className="w-8 h-8 text-yellow-500 absolute top-4 right-4 animate-bounce" />
                </div>
                <h3 className="text-2xl font-bold text-text-primary mb-3">准备好生成您的智能体了吗？</h3>
                <p className="text-sm text-text-tertiary max-w-md leading-relaxed">
                  点击左侧按钮开始生成用户画像。OASIS 将基于真实数据特征，通过 LLM 扩展生成具有丰富性格、背景和兴趣的百万级智能体群体。
                </p>
                <div className="mt-10 grid grid-cols-2 gap-6 w-full max-w-lg">
                  <div className="p-5 rounded-2xl bg-bg-primary/50 border border-border-default text-left hover:border-accent/30 transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-accent-subtle flex items-center justify-center mb-3">
                      <Globe className="w-4 h-4 text-accent" />
                    </div>
                    <p className="text-xs font-bold text-text-primary mb-1">真实性与文化对齐</p>
                    <p className="text-xs text-text-muted">基于真实社交媒体种子，结合选择的国际地区生成本地化特征</p>
                  </div>
                  <div className="p-5 rounded-2xl bg-bg-primary/50 border border-border-default text-left hover:border-blue-500/30 transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center mb-3">
                      <Database className="w-4 h-4 text-blue-500" />
                    </div>
                    <p className="text-xs font-bold text-text-primary mb-1">多维兴趣与性格</p>
                    <p className="text-xs text-text-muted">LLM 自动生成符合 Topic 设定的 MBTI、Bio 及深层兴趣标签</p>
                  </div>
                </div>
              </div>
            ) : (
              <Table>
                <TableHeader className="bg-bg-primary/50 sticky top-0 z-10">
                  <TableRow className="border-border-default hover:bg-transparent">
                    <TableHead className="w-24">ID</TableHead>
                    <TableHead className="w-32">姓名</TableHead>
                    <TableHead>Bio 预览</TableHead>
                    <TableHead className="w-48">兴趣标签</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((agent) => (
                    <TableRow key={agent.id} className="border-border-default hover:bg-bg-tertiary/30 transition-colors">
                      <TableCell className="font-mono text-xs text-accent">{agent.id}</TableCell>
                      <TableCell className="font-bold text-text-primary">{agent.name}</TableCell>
                      <TableCell className="text-xs text-text-secondary max-w-xs truncate italic">“{agent.bio}”</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {agent.interests.map((tag: string) => (
                            <Badge key={tag} variant="outline" className="text-[9px] bg-bg-primary border-border-default text-text-tertiary py-0 h-4">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </Card>
      </div>
      </div>
    </div>
  );
}
