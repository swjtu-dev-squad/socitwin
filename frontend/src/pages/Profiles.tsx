import { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Slider,
} from '@/components/ui';
import {
  Activity,
  BrainCircuit,
  Database,
  FileJson,
  Network,
  PlayCircle,
  Share2,
  Sparkles,
  Users,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { SubscriptionPanel, type DatasetPlatform } from '@/components/SubscriptionPanel';
import { SocialKnowledgeGraph } from '@/components/SocialKnowledgeGraph';
import { useTopics } from '@/hooks/useSimulationData';
import { simulationApi } from '@/lib/api';
import type { TopicContentSeed, TopicDetail, TopicProfileSeed } from '@/lib/types';

function buildGraphData(
  topic: TopicDetail,
  profiles: TopicProfileSeed[],
  contents: TopicContentSeed[],
) {
  const topicNodeId = `topic:${topic.id}`;
  const nodes = [
    {
      id: topicNodeId,
      name: topic.name,
      type: 'topic',
      heat: topic.trend_rank ? `#${topic.trend_rank}` : 'LIVE',
      source: topic.platform || 'twitter',
    },
    ...profiles.map((profile) => ({
      id: profile.external_user_id,
      name: profile.display_name || profile.username || profile.external_user_id,
      bio: profile.bio || profile.agent_config.description,
      interests: profile.interests,
      type: 'user',
    })),
  ];

  const edges: Array<{ source: string; target: string; type: string }> = profiles.map(
    (profile) => ({
      source: profile.external_user_id,
      target: topicNodeId,
      type: 'topic_link',
    }),
  );

  const contentAuthorMap = new Map<string, string>();
  contents.forEach((content) => {
    if (content.external_content_id && content.author_external_user_id) {
      contentAuthorMap.set(content.external_content_id, content.author_external_user_id);
    }
  });

  const existingEdges = new Set(
    edges.map((edge) => `${edge.source}->${edge.target}:${edge.type}`),
  );
  contents.forEach((content) => {
    if (!content.author_external_user_id || !content.parent_external_content_id) {
      return;
    }

    const parentAuthor = contentAuthorMap.get(content.parent_external_content_id);
    if (!parentAuthor || parentAuthor === content.author_external_user_id) {
      return;
    }

    const edgeKey = `${content.author_external_user_id}->${parentAuthor}:follow`;
    if (existingEdges.has(edgeKey)) {
      return;
    }

    existingEdges.add(edgeKey);
    edges.push({
      source: content.author_external_user_id,
      target: parentAuthor,
      type: 'follow',
    });
  });

  return { nodes, edges };
}

export default function Profiles() {
  const navigate = useNavigate();
  const [selectedPlatform, setSelectedPlatform] = useState<DatasetPlatform>('twitter');
  const { data: topics, isLoading: topicsLoading } = useTopics(selectedPlatform);
  const [genStatus, setGenStatus] = useState<'idle' | 'generating' | 'completed'>('idle');
  const [algorithm, setAlgorithm] = useState('persona-llm');
  const [count, setCount] = useState([1500]);
  const [selectedTopic, setSelectedTopic] = useState('');
  const [stats, setStats] = useState({ userCount: 0, linkCount: 0, density: 0 });
  const [generatedData, setGeneratedData] = useState<any>(null);

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
    setGenStatus('idle');
    setGeneratedData(null);
    setStats({ userCount: 0, linkCount: 0, density: 0 });
  }, [selectedPlatform, selectedTopic]);

  const selectedTopicMeta = useMemo(
    () => topics.find((topic) => topic.id === selectedTopic) || null,
    [topics, selectedTopic],
  );
  const selectedTopicLabel = selectedTopicMeta?.name || '';

  const handleGenerate = async () => {
    if (!selectedTopic) {
      toast.error('请先选择一个话题');
      return;
    }

    setGenStatus('generating');

    try {
      const response = await simulationApi.getTopicSimulation(selectedTopic, {
        platform: selectedPlatform,
        participant_limit: Math.min(count[0], 500),
        content_limit: Math.min(Math.max(count[0] * 2, 40), 500),
      });

      const result = response.data;
      const graphData = buildGraphData(result.topic, result.profiles, result.contents);
      const nodeCount = graphData.nodes.length;
      const edgeCount = graphData.edges.length;
      const maxEdges = nodeCount > 1 ? (nodeCount * (nodeCount - 1)) / 2 : 1;
      const density = Number(((edgeCount / maxEdges) * 100).toFixed(1));

      setGeneratedData(graphData);
      setStats({
        userCount: result.participant_count,
        linkCount: edgeCount,
        density,
      });
      setGenStatus('completed');
      toast.success(`已完成话题画像预处理: ${result.topic.name}`);
    } catch (error) {
      console.error('Generation error:', error);
      toast.error('画像预处理失败，请检查后端服务');
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
          <p className="text-text-tertiary mt-1">基于真实种子数据与话题预处理结果生成仿真社会网络</p>
        </div>
        {genStatus === 'completed' && (
          <Button
            variant="outline"
            className="rounded-xl border-accent text-accent h-10 gap-2"
            onClick={() =>
              navigate('/overview', {
                state: {
                  selectedPlatform,
                  selectedTopic,
                },
              })
            }
          >
            <PlayCircle className="w-4 h-4" />
            应用并启动仿真
          </Button>
        )}
      </header>

      <SubscriptionPanel
        selectedPlatform={selectedPlatform}
        onPlatformChange={setSelectedPlatform}
        topicCount={topics.length}
      />

      <div className="grid grid-cols-12 gap-8">
        <Card className="col-span-4 bg-bg-secondary border-border-default p-6 space-y-6">
          <section className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-accent flex items-center gap-2">
              <Database className="w-4 h-4" /> 1. 原始种子数据
            </h3>

            <div className="space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">
                话题来源
              </div>
              <Select value={selectedTopic} onValueChange={setSelectedTopic}>
                <SelectTrigger className="bg-bg-primary border-border-default h-12 rounded-xl">
                  <SelectValue
                    placeholder={topicsLoading ? '加载话题中...' : '选择话题'}
                    value={selectedTopicLabel}
                  />
                </SelectTrigger>
                <SelectContent>
                  {topics.map((topic) => (
                    <SelectItem key={topic.id} value={topic.id}>
                      {topic.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-3">
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl hover:border-accent/50 transition-all">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <FileJson className="w-4 h-4 text-blue-400" /> 真实用户样本
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    已加载: {selectedTopicMeta?.user_count ?? 0}条
                  </Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl hover:border-accent/50 transition-all">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Activity className="w-4 h-4 text-rose-400" /> 话题/语义字典
                  </span>
                  <Badge variant="outline" className="text-[10px]">已加载: {topics.length}个</Badge>
                </div>
              </div>
              <div className="p-3 bg-bg-primary border border-border-default rounded-xl hover:border-accent/50 transition-all">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium flex items-center gap-2">
                    <Network className="w-4 h-4 text-emerald-400" /> 原始社交拓扑
                  </span>
                  <Badge variant="outline" className="text-[10px]">
                    {genStatus === 'completed' ? `已生成: ${stats.linkCount}条` : '待生成'}
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
                  <div className="text-[10px] text-text-muted">
                    基于话题参与者的真实行为痕迹生成仿真画像
                  </div>
                </SelectItem>
                <SelectItem value="ba-structural">
                  <div className="font-bold">Structural Preferential Attachment</div>
                  <div className="text-[10px] text-text-muted">
                    侧重于生成具有幂律分布特征的复杂社交网络
                  </div>
                </SelectItem>
                <SelectItem value="semantic-homophily">
                  <div className="font-bold">Semantic Homophily</div>
                  <div className="text-[10px] text-text-muted">
                    基于兴趣语义相似度建立社交连接
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </section>

          <section className="space-y-4">
            <div className="flex justify-between">
              <h3 className="text-xs font-bold uppercase tracking-widest text-text-tertiary">预处理规模</h3>
              <span className="font-mono text-accent">{count[0].toLocaleString()} Agents</span>
            </div>
            <Slider value={count} onValueChange={setCount} min={10} max={10000} step={100} />
          </section>

          <Button
            className="w-full h-14 rounded-2xl bg-accent hover:bg-accent-hover shadow-lg shadow-accent/20 font-bold gap-2"
            onClick={handleGenerate}
            disabled={genStatus === 'generating' || !selectedTopic}
          >
            {genStatus === 'generating' ? (
              <>
                <div className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                预处理中...
              </>
            ) : (
              '开始生成社交网络'
            )}
          </Button>
        </Card>

        <div className="col-span-8 space-y-6">
          <div className="grid grid-cols-3 gap-4">
            <StatsCard label="拟合用户总数" value={stats.userCount} icon={Users} />
            <StatsCard label="生成关系边" value={stats.linkCount} icon={Share2} />
            <StatsCard label="图密度 (Density)" value={stats.density + '%'} icon={Network} />
          </div>

          <Card className="bg-bg-secondary border-border-default overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
              <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary">
                社交知识图谱预览 (Social Knowledge Graph)
              </h2>
              <div className="flex gap-2">
                <Badge variant="secondary" className="text-[9px]">Node: Agent</Badge>
                <Badge variant="outline" className="text-[9px] border-emerald-500/30 text-emerald-400">
                  Edge: Interest
                </Badge>
                <Badge variant="outline" className="text-[9px] border-blue-500/30 text-blue-400">
                  Edge: Follow
                </Badge>
              </div>
            </div>
            <div className="flex-1 bg-bg-primary/30 relative">
              <SocialKnowledgeGraph data={generatedData} />

              {genStatus === 'idle' && (
                <div className="absolute inset-0 flex items-center justify-center backdrop-blur-sm bg-bg-primary/40">
                  <p className="text-text-muted text-sm border border-border-default px-6 py-3 rounded-full bg-bg-secondary">
                    选择平台和话题并点击生成以查看图谱
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
