import { useState, useMemo } from 'react';
import { Card, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Slider, Badge, Tabs, TabsList, TabsTrigger, Input } from '@/components/ui';
import { Database, Network, BrainCircuit, Users, Share2, Sparkles, Activity, PlayCircle, FileText, RefreshCw, X } from 'lucide-react';
import { SocialKnowledgeGraph } from '@/components/SocialKnowledgeGraph';
import { SubscriptionPanel } from '@/components/SubscriptionPanel';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

export default function Profiles() {
  const navigate = useNavigate();
  const [genStatus, setGenStatus] = useState<'idle' | 'generating' | 'completed'>('idle');
  const [algorithm, setAlgorithm] = useState('persona-llm');
  const [count, setCount] = useState([1500]);

  // Persona 数据相关状态
  const [selectedPlatform, setSelectedPlatform] = useState<string>('');
  const [personaStats, setPersonaStats] = useState<{
    users: number;
    posts: number;
    replies: number;
    relationships: number;
    networks: number;
    topics: number;
  } | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // 模拟生成的统计数据
  const [stats, setStats] = useState({ userCount: 0, linkCount: 0, density: 0 });
  const [generatedData, setGeneratedData] = useState<any>(null);

  // 获取平台统计数据
  const fetchPersonaStats = async (platform: string) => {
    if (!platform) return;
    setLoadingStats(true);
    try {
      const response = await fetch(`/api/persona/${platform}/stats`);
      if (!response.ok) {
        throw new Error('Failed to fetch stats');
      }
      const data = await response.json();
      setPersonaStats(data.stats);
      toast.success(`已加载 ${platform} 平台数据统计`);
    } catch (error) {
      console.error('Fetch stats error:', error);
      toast.error('获取统计数据失败');
      setPersonaStats(null);
    } finally {
      setLoadingStats(false);
    }
  };

  // 平台选择变化时获取统计
  const handlePlatformChange = (platform: string) => {
    setSelectedPlatform(platform);
    fetchPersonaStats(platform);
  };

  const handleGenerate = async () => {
    setGenStatus('generating');
    
    try {
      const response = await fetch('/api/users/generate_advanced', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userSeedPath: 'default_users.json',
          topicSeedPath: 'default_topics.json',
          algoType: algorithm,
          agentCount: count[0],
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to generate social network');
      }

      const result = await response.json();
      setGeneratedData({ nodes: result.nodes, edges: result.edges });
      setStats(result.stats);
      setGenStatus('completed');
      toast.success(`成功基于 ${algorithm} 算法生成社交网络`);
    } catch (error) {
      console.error('Generation error:', error);
      toast.error('生成社交网络失败，请检查后端服务');
      setGenStatus('idle');
    }
  };

  return (
    <div className="px-6 lg:px-12 py-12 space-y-8">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <BrainCircuit className="w-10 h-10 text-accent" />
            仿真画像实验室
          </h1>
          <p className="text-text-tertiary mt-1">基于真实种子数据与进化算法生成百万级仿真社会网络</p>
        </div>
        {genStatus === 'completed' && (
          <Button variant="outline" className="rounded-xl border-accent text-accent h-10 gap-2" onClick={() => navigate('/overview')}>
            <PlayCircle className="w-4 h-4" />
            应用并启动仿真
          </Button>
        )}
      </header>

      {/* 新增：数据订阅中心 */}
      <SubscriptionPanel />

      <div className="grid grid-cols-12 gap-8">
        {/* 左侧：精细化控制面板 */}
        <Card className="col-span-4 bg-bg-secondary border-border-default p-6 space-y-6">
          <section className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-accent flex items-center gap-2">
              <Database className="w-4 h-4" /> 1. 原始种子数据
            </h3>

            {/* 平台选择器 */}
            <div className="space-y-3">
              {selectedPlatform ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 px-3 py-2 bg-accent/10 border border-accent/30 rounded-xl flex-1">
                    <span className="text-xs font-medium text-accent flex-1">
                      {{ twitter: 'X / Twitter', reddit: 'Reddit', tiktok: 'TikTok', instagram: 'Instagram', facebook: 'Facebook' }[selectedPlatform]}
                    </span>
                    <button
                      onClick={() => { setSelectedPlatform(''); setPersonaStats(null); }}
                      className="text-text-tertiary hover:text-text-primary transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-9 w-9 rounded-xl border-border-default"
                    onClick={() => fetchPersonaStats(selectedPlatform)}
                    disabled={loadingStats}
                  >
                    <RefreshCw className={`w-4 h-4 ${loadingStats ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              ) : (
                <Select value={selectedPlatform} onValueChange={handlePlatformChange}>
                  <SelectTrigger className="bg-bg-primary border-border-default h-10 rounded-xl">
                    <SelectValue placeholder="选择数据平台" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="twitter">X / Twitter</SelectItem>
                    <SelectItem value="reddit">Reddit</SelectItem>
                    <SelectItem value="tiktok">TikTok</SelectItem>
                    <SelectItem value="instagram">Instagram</SelectItem>
                    <SelectItem value="facebook">Facebook</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* 数据统计展示 */}
            <div className="space-y-2">
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Users className="w-4 h-4 text-blue-400" /> 用户数据
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {personaStats?.users?.toLocaleString() ?? '未选择'}
                  </Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <FileText className="w-4 h-4 text-rose-400" /> 帖子数据
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {personaStats?.posts?.toLocaleString() ?? '未选择'}
                  </Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-400" /> 回复数据
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {personaStats?.replies?.toLocaleString() ?? '未选择'}
                  </Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Network className="w-4 h-4 text-purple-400" /> 关系数据
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {personaStats?.relationships?.toLocaleString() ?? '未选择'}
                  </Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Share2 className="w-4 h-4 text-orange-400" /> 网络数据
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {personaStats?.networks?.toLocaleString() ?? '未选择'}
                  </Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-yellow-400" /> 话题分类
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {personaStats?.topics ?? '未选择'}
                  </Badge>
                </div>
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-accent flex items-center gap-2">
              <Sparkles className="w-4 h-4" /> 2. 生成策略算法
            </h3>
            <Select value={algorithm} onValueChange={setAlgorithm}>
              <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                <SelectValue placeholder="选择生成算法" value={algorithm} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="persona-llm">
                  <div className="font-bold">Persona-LLM (深层特征)</div>
                  <div className="text-[10px] text-text-muted">利用LLM幻化出具有真实人格、价值观的Agent</div>
                </SelectItem>
                <SelectItem value="ba-structural">
                  <div className="font-bold">Structural Preferential Attachment</div>
                  <div className="text-[10px] text-text-muted">侧重于生成具有幂律分布特征的复杂社交网络</div>
                </SelectItem>
                <SelectItem value="semantic-homophily">
                  <div className="font-bold">Semantic Homophily</div>
                  <div className="text-[10px] text-text-muted">基于兴趣语义相似度建立社交连接</div>
                </SelectItem>
              </SelectContent>
            </Select>
          </section>

          <section className="space-y-4">
            <div className="flex justify-between">
              <h3 className="text-xs font-bold uppercase tracking-widest text-text-tertiary">生成规模</h3>
              <span className="font-mono text-accent">{count[0].toLocaleString()} Agents</span>
            </div>
            <Slider value={count} onValueChange={setCount} min={10} max={10000} step={100} />
          </section>

          <Button 
            className="w-full h-14 rounded-2xl bg-accent hover:bg-accent-hover shadow-lg shadow-accent/20 font-bold gap-2"
            onClick={handleGenerate}
            disabled={genStatus === 'generating'}
          >
            {genStatus === 'generating' ? (
              <>
                <div className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                进化计算中...
              </>
            ) : '开始生成社交网络'}
          </Button>
        </Card>

        {/* 右侧：预览与社交知识图谱 */}
        <div className="col-span-8 space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <StatsCard label="拟合用户总数" value={stats.userCount} icon={Users} />
            <StatsCard label="生成关系边" value={stats.linkCount} icon={Share2} />
            <StatsCard label="图密度 (Density)" value={stats.density + "%"} icon={Network} />
          </div>

          <Card className="bg-bg-secondary border-border-default overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
              <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary">社交知识图谱预览 (Social Knowledge Graph)</h2>
              <div className="flex gap-2">
                 <Badge variant="secondary" className="text-[9px]">Node: Agent</Badge>
                 <Badge variant="outline" className="text-[9px] border-emerald-500/30 text-emerald-400">Edge: Interest</Badge>
                 <Badge variant="outline" className="text-[9px] border-blue-500/30 text-blue-400">Edge: Follow</Badge>
              </div>
            </div>
            <div className="flex-1 bg-bg-primary/30 relative">
              {/* 这里调用力导向图组件 */}
              <SocialKnowledgeGraph data={generatedData} />
              
              {genStatus === 'idle' && (
                <div className="absolute inset-0 flex items-center justify-center backdrop-blur-sm bg-bg-primary/40">
                  <p className="text-text-muted text-sm border border-border-default px-6 py-3 rounded-full bg-bg-secondary">
                    配置左侧参数并点击生成以查看图谱
                  </p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatsCard({ label, value, icon: Icon }: any) {
  return (
    <Card className="p-4 bg-bg-secondary border-border-default flex items-center gap-4">
      <div className="p-3 bg-bg-primary rounded-xl border border-border-default text-accent">
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-[10px] font-bold text-text-tertiary uppercase tracking-tighter">{label}</p>
        <p className="text-2xl font-mono font-bold">{value}</p>
      </div>
    </Card>
  );
}
