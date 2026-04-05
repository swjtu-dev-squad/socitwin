import { useEffect, useMemo, useState } from 'react';
import {
  Database,
  Network,
  BrainCircuit,
  Users,
  Share2,
  Sparkles,
  Activity,
  PlayCircle,
  FileText,
  RefreshCw,
  GitBranch,
} from 'lucide-react';
import { Card, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Badge, Input } from '@/components/ui';
import { SocialKnowledgeGraph } from '@/components/SocialKnowledgeGraph';
import { SubscriptionPanel, type SubscriptionPlatformCard } from '@/components/SubscriptionPanel';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import {
  generateDatasetArtifacts,
  getGeneratedGraph,
  getPersonaDataset,
  listPersonaDatasets,
} from '@/lib/personaApi';
import type { GeneratedGraphRecord, PersonaDatasetSummary } from '@/lib/types';

type PersonaDatasetDetail = PersonaDatasetSummary & {
  latest_graph?: {
    generation_id: string;
    algorithm: string;
    stats: GeneratedGraphRecord['stats'];
    created_at: string;
  } | null;
};

type SeedMetricDescriptor = {
  key: keyof typeof EMPTY_COUNTS;
  label: string;
  value: number;
  icon: any;
  colorClass: string;
};

const EMPTY_COUNTS = {
  users: 0,
  posts: 0,
  replies: 0,
  relationships: 0,
  networks: 0,
  topics: 0,
};

const ALGORITHM_DESCRIPTIONS: Record<string, string> = {
  'real-seed-fusion': '真实种子优先，先保留已有互动与结构线索，再用最小必要补边生成稳定图谱。',
  'persona-llm': '利用真实用户画像和文本特征补全 persona，再生成更像人的仿真 agent。',
  'ba-structural': '结构优先，适合在真实关系稀疏时补出更完整的网络骨架。',
  'semantic-homophily': '基于兴趣语义相似度与真实互动边混合生成关系网络。',
};

const ALGORITHM_OUTPUTS: Record<string, string[]> = {
  'real-seed-fusion': ['保留真实种子结构', '最小必要补边', '稳定输出图谱'],
  'persona-llm': ['拟合用户画像', '补全 agent 设定', '生成初始关系图'],
  'ba-structural': ['补齐关系边', '强化网络骨架', '提升连通性'],
  'semantic-homophily': ['基于兴趣连边', '混合真实互动', '优化图密度'],
};

const ALGORITHM_SEED_KEYS = {
  'real-seed-fusion': ['users', 'posts', 'replies', 'topics'],
  'persona-llm': ['users', 'posts', 'replies', 'topics'],
  'semantic-homophily': ['users', 'posts', 'replies', 'topics'],
  'ba-structural': ['users', 'posts', 'replies', 'topics', 'relationships', 'networks'],
} as const;

const SEED_METRIC_META = {
  users: { label: '种子用户', icon: Users, colorClass: 'text-blue-400' },
  posts: { label: '种子帖子', icon: FileText, colorClass: 'text-rose-400' },
  replies: { label: '种子回复', icon: Activity, colorClass: 'text-emerald-400' },
  relationships: { label: '真实关系', icon: Network, colorClass: 'text-purple-400' },
  networks: { label: '网络结构', icon: Share2, colorClass: 'text-orange-400' },
  topics: { label: '话题标签', icon: Sparkles, colorClass: 'text-yellow-400' },
} as const;

const PLATFORM_META = [
  { id: 'twitter', name: 'X / Twitter', colorClass: 'text-blue-400' },
  { id: 'reddit', name: 'Reddit', colorClass: 'text-orange-500' },
  { id: 'tiktok', name: 'TikTok', colorClass: 'text-pink-500' },
  { id: 'instagram', name: 'Instagram', colorClass: 'text-purple-500' },
  { id: 'facebook', name: 'Facebook', colorClass: 'text-blue-600' },
] as const;

const PLATFORM_LABELS = Object.fromEntries(PLATFORM_META.map((platform) => [platform.id, platform.name])) as Record<string, string>;

function formatNumber(value: number | undefined | null) {
  if (value == null) return '0';
  return value.toLocaleString();
}

function formatBeijingTime(value: string | undefined | null) {
  if (!value) return '未同步';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
    .format(date)
    .replace(/\//g, '-');
}

function formatDatasetOption(dataset: PersonaDatasetSummary) {
  return `${formatBeijingTime(dataset.created_at)} | ${dataset.dataset_id}`;
}

function formatDatasetTrendSummary(dataset: PersonaDatasetSummary) {
  const trends = Array.isArray(dataset.meta?.trends_processed)
    ? dataset.meta.trends_processed.filter((item: unknown): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  if (trends.length === 0) return dataset.label;
  const shown = trends.slice(0, 3);
  const suffix = trends.length > shown.length ? ` +${trends.length - shown.length}` : '';
  return `${shown.join(' / ')}${suffix}`;
}

function datasetSnapshotTimestamp(dataset: Pick<PersonaDatasetSummary, 'created_at' | 'updated_at'>) {
  const createdAt = new Date(dataset.created_at).getTime();
  if (Number.isFinite(createdAt) && createdAt > 0) return createdAt;
  const updatedAt = new Date(dataset.updated_at).getTime();
  return Number.isFinite(updatedAt) ? updatedAt : 0;
}

function formatDensityPercent(value: number | undefined) {
  return `${((value || 0) * 100).toFixed(2)}%`;
}

export default function Profiles() {
  const navigate = useNavigate();

  const [selectedPlatform, setSelectedPlatform] = useState<string>('');
  const [datasets, setDatasets] = useState<PersonaDatasetSummary[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [selectedDataset, setSelectedDataset] = useState<PersonaDatasetDetail | null>(null);
  const [generatedGraph, setGeneratedGraph] = useState<GeneratedGraphRecord | null>(null);
  const [currentGenerationId, setCurrentGenerationId] = useState<string | null>(null);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetDetailLoading, setDatasetDetailLoading] = useState(false);
  const [generationLoading, setGenerationLoading] = useState(false);
  const [subscriptionLoadingPlatform, setSubscriptionLoadingPlatform] = useState<string | null>(null);
  const [liveSubscriptions, setLiveSubscriptions] = useState<Record<string, boolean>>({
    twitter: false,
    reddit: false,
    tiktok: false,
    instagram: false,
    facebook: false,
  });
  const [algorithm, setAlgorithm] = useState('real-seed-fusion');
  const [agentCount, setAgentCount] = useState('0');

  const platformDatasets = useMemo(
    () =>
      datasets
        .filter((dataset) => dataset.recsys_type === selectedPlatform)
        .sort((left, right) => datasetSnapshotTimestamp(right) - datasetSnapshotTimestamp(left)),
    [datasets, selectedPlatform],
  );

  const latestDatasetsByPlatform = useMemo(
    () =>
      datasets.reduce<Record<string, PersonaDatasetSummary>>((acc, dataset) => {
        const existing = acc[dataset.recsys_type];
        if (!existing || datasetSnapshotTimestamp(dataset) > datasetSnapshotTimestamp(existing)) {
          acc[dataset.recsys_type] = dataset;
        }
        return acc;
      }, {}),
    [datasets],
  );

  const latestPlatformDataset = latestDatasetsByPlatform[selectedPlatform] || null;
  const selectedDatasetOption = platformDatasets.find((dataset) => dataset.dataset_id === selectedDatasetId) || null;

  const graphStats = useMemo(
    () => ({
      userCount: generatedGraph?.stats.agentCount || 0,
      linkCount: generatedGraph?.stats.edgeCount || 0,
      densityLabel: formatDensityPercent(generatedGraph?.stats.density),
    }),
    [generatedGraph],
  );

  const selectedCounts = selectedDataset?.counts || EMPTY_COUNTS;
  const visibleSeedMetrics = useMemo<SeedMetricDescriptor[]>(
    () =>
      ALGORITHM_SEED_KEYS[algorithm].map((key) => ({
        key,
        ...SEED_METRIC_META[key],
        value: selectedCounts[key],
      })),
    [algorithm, selectedCounts],
  );

  const platformCards = useMemo<SubscriptionPlatformCard[]>(
    () =>
      PLATFORM_META.map((platform) => {
        const latestDataset = latestDatasetsByPlatform[platform.id];
        const datasetCount = datasets.filter((dataset) => dataset.recsys_type === platform.id).length;
        const checked = liveSubscriptions[platform.id];

        return {
          id: platform.id,
          name: platform.name,
          status: subscriptionLoadingPlatform === platform.id ? 'syncing' : checked ? 'connected' : 'standby',
          latency: latestDataset ? formatBeijingTime(latestDataset.created_at).split(' ')[1] || 'ready' : '-',
          progress: subscriptionLoadingPlatform === platform.id ? 65 : checked ? 100 : 0,
          checked,
          canToggle: true,
          datasets: datasetCount,
          note:
            subscriptionLoadingPlatform === platform.id
              ? '正在读取可用数据集。'
              : datasetCount > 0
                ? `已发现 ${datasetCount} 份数据集。`
                : '暂未发现可用数据集。',
          lastDatasetId: latestDataset?.dataset_id,
          colorClass: platform.colorClass,
        };
      }),
    [datasets, latestDatasetsByPlatform, liveSubscriptions, subscriptionLoadingPlatform],
  );

  const loadDatasets = async (preferredDatasetId?: string) => {
    setDatasetsLoading(true);
    try {
      const { datasets: items } = await listPersonaDatasets();
      setDatasets(items);

      if (preferredDatasetId) {
        setSelectedDatasetId(preferredDatasetId);
      }
      return items;
    } catch (error) {
      console.error('Load datasets error:', error);
      toast.error('加载数据集列表失败');
      setDatasets([]);
      return [] as PersonaDatasetSummary[];
    } finally {
      setDatasetsLoading(false);
    }
  };

  const loadDatasetDetail = async (datasetId: string) => {
    if (!datasetId) {
      setSelectedDataset(null);
      setGeneratedGraph(null);
      setCurrentGenerationId(null);
      return;
    }

    setDatasetDetailLoading(true);
    try {
      const { dataset } = await getPersonaDataset(datasetId);
      const detail = dataset as PersonaDatasetDetail;
      setSelectedDataset(detail);
      setAgentCount(String(detail.counts.users || 0));

      if (detail.latest_generation_id) {
        const { graph } = await getGeneratedGraph(detail.latest_generation_id);
        setGeneratedGraph(graph);
        setCurrentGenerationId(detail.latest_generation_id);
      } else {
        setGeneratedGraph(null);
        setCurrentGenerationId(null);
      }
    } catch (error) {
      console.error('Load dataset detail error:', error);
      toast.error('加载数据集详情失败');
      setSelectedDataset(null);
      setGeneratedGraph(null);
      setCurrentGenerationId(null);
    } finally {
      setDatasetDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!liveSubscriptions[selectedPlatform]) {
      if (selectedDatasetId) setSelectedDatasetId('');
      setSelectedDataset(null);
      setGeneratedGraph(null);
      setCurrentGenerationId(null);
      return;
    }

    if (!platformDatasets.length) {
      if (selectedDatasetId) setSelectedDatasetId('');
      return;
    }

    if (!platformDatasets.some((dataset) => dataset.dataset_id === selectedDatasetId)) {
      setSelectedDatasetId(platformDatasets[0].dataset_id);
    }
  }, [platformDatasets, selectedDatasetId]);

  useEffect(() => {
    loadDatasetDetail(selectedDatasetId).catch(() => {
      // Error handled in loadDatasetDetail.
    });
  }, [selectedDatasetId]);

  const handleTogglePlatform = async (platformId: string, checked: boolean) => {
    const platformName = PLATFORM_LABELS[platformId] || platformId;
    if (!checked) {
      setLiveSubscriptions({
        twitter: false,
        reddit: false,
        tiktok: false,
        instagram: false,
        facebook: false,
      });
      setSelectedPlatform('');
      setSelectedDatasetId('');
      setSelectedDataset(null);
      setGeneratedGraph(null);
      setCurrentGenerationId(null);
      toast.success(`已取消 ${platformName} 数据集订阅视图`);
      return;
    }

    setSubscriptionLoadingPlatform(platformId);
    try {
      setSelectedPlatform(platformId);
      setSelectedDatasetId('');
      setSelectedDataset(null);
      setGeneratedGraph(null);
      setCurrentGenerationId(null);
      const items = await loadDatasets();
      const subscribedDatasets = items.filter((dataset) => dataset.recsys_type === platformId);
      setLiveSubscriptions({
        twitter: false,
        reddit: false,
        tiktok: false,
        instagram: false,
        facebook: false,
        [platformId]: true,
      });
      if (subscribedDatasets[0]?.dataset_id) {
        setSelectedDatasetId(subscribedDatasets[0].dataset_id);
        toast.success(`已载入 ${subscribedDatasets.length} 份 ${platformName} 数据集`);
      } else {
        setSelectedDatasetId('');
        setSelectedDataset(null);
        setGeneratedGraph(null);
        setCurrentGenerationId(null);
        toast.info(`${platformName} 暂无可用数据集`);
      }
    } catch (error) {
      console.error('Load platform datasets error:', error);
      setLiveSubscriptions({
        twitter: false,
        reddit: false,
        tiktok: false,
        instagram: false,
        facebook: false,
      });
      setSelectedPlatform('');
      toast.error((error as Error).message || '载入数据集失败');
    } finally {
      setSubscriptionLoadingPlatform(null);
    }
  };

  const handleRefresh = async () => {
    if (!selectedPlatform || !liveSubscriptions[selectedPlatform]) {
      toast.info('请先订阅一个平台');
      return;
    }
    await loadDatasets(selectedDatasetId || undefined);
    toast.success('已刷新数据集列表');
  };

  const handleGenerate = async () => {
    if (!selectedDatasetId) {
      toast.error('请先订阅并选择一个数据集');
      return;
    }

    setGenerationLoading(true);
    try {
      const result = await generateDatasetArtifacts(selectedDatasetId, {
        algorithm,
        agentCount: Math.max(1, Number(agentCount) || selectedDataset?.counts.users || 1),
      });
      setGeneratedGraph(result.graph);
      setCurrentGenerationId(result.generation_id);
      await loadDatasets(selectedDatasetId);
      toast.success(`已基于 ${selectedDatasetId} 生成社交网络`);
    } catch (error) {
      console.error('Generation error:', error);
      toast.error((error as Error).message || '生成社交网络失败');
    } finally {
      setGenerationLoading(false);
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
          <p className="text-text-tertiary mt-1">选择算法种子数据，配置生成策略算法，输出社交知识图谱与关键指标</p>
        </div>
        {generatedGraph && (
          <Button variant="outline" className="rounded-xl border-accent text-accent h-10 gap-2" onClick={() => navigate('/overview')}>
            <PlayCircle className="w-4 h-4" />
            应用并启动仿真
          </Button>
        )}
      </header>

      <SubscriptionPanel
        platforms={platformCards}
        selectedPlatform={selectedPlatform}
        refreshing={datasetsLoading || subscriptionLoadingPlatform !== null}
        onSelectPlatform={(platformId) => {
          if (liveSubscriptions[platformId]) {
            setSelectedPlatform(platformId);
          }
        }}
        onTogglePlatform={(platformId, checked) => {
          void handleTogglePlatform(platformId, checked);
        }}
        onRefresh={() => {
          void handleRefresh();
        }}
      />

      <div className="grid grid-cols-12 gap-8">
        <Card className="col-span-12 lg:col-span-4 bg-bg-secondary border-border-default p-6 space-y-6">
          <section className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-accent flex items-center gap-2">
              <Database className="w-4 h-4" /> 1. 算法种子数据
            </h3>

            <div className="rounded-2xl border border-accent/30 bg-accent/5 p-4 space-y-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-bold">当前平台：{PLATFORM_LABELS[selectedPlatform] || selectedPlatform || '未选择'}</span>
                <Badge variant="outline">{platformDatasets.length} datasets</Badge>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">选择数据集</label>
              <Select value={selectedDatasetId} onValueChange={setSelectedDatasetId}>
                <SelectTrigger className="bg-bg-primary border-border-default h-auto min-h-[64px] rounded-xl py-3">
                  {selectedDatasetOption ? (
                    <div className="min-w-0 pr-4 text-left">
                      <div className="text-xs font-bold leading-tight">{formatBeijingTime(selectedDatasetOption.created_at)}</div>
                      <div className="mt-1 break-all font-mono text-[10px] leading-tight text-text-tertiary">
                        {selectedDatasetOption.dataset_id}
                      </div>
                      <div className="mt-1 whitespace-normal break-words text-[10px] leading-snug text-text-muted">
                        {formatDatasetTrendSummary(selectedDatasetOption)}
                      </div>
                    </div>
                  ) : (
                    <SelectValue placeholder={datasetsLoading ? '数据集加载中...' : '请先订阅平台，再选择已同步的数据集'} />
                  )}
                </SelectTrigger>
                <SelectContent>
                  {platformDatasets.map((dataset) => (
                    <SelectItem key={dataset.dataset_id} value={dataset.dataset_id}>
                      <div className="pr-6">
                        <div className="font-bold leading-tight">{formatBeijingTime(dataset.created_at)}</div>
                        <div className="mt-1 break-all font-mono text-[10px] leading-tight text-text-muted">
                          {dataset.dataset_id}
                        </div>
                        <div className="mt-1 whitespace-normal break-words text-[10px] leading-snug text-text-muted">
                          {formatDatasetTrendSummary(dataset)}
                        </div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <InfoMetric label="最新快照时间" value={latestPlatformDataset ? formatBeijingTime(latestPlatformDataset.created_at) : '暂无'} />
              <InfoMetric label="最新 dataset_id" value={latestPlatformDataset?.dataset_id || '暂无'} mono />
            </div>

            <Button
              variant="outline"
              className="w-full gap-2"
              onClick={() => {
                void handleRefresh();
              }}
              disabled={datasetsLoading}
            >
              <RefreshCw className={`w-4 h-4 ${datasetsLoading ? 'animate-spin' : ''}`} />
              刷新数据集列表
            </Button>

            {selectedDataset ? (
              <div className="rounded-2xl border border-border-default bg-bg-primary p-4 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold">{selectedDataset.label}</p>
                    <p className="text-[11px] text-text-muted font-mono break-all">{selectedDataset.dataset_id}</p>
                  </div>
                  <Badge variant="secondary">{selectedDataset.status.toUpperCase()}</Badge>
                </div>
                <div className="text-[11px] text-text-tertiary space-y-1">
                  <p>采集时间：{formatBeijingTime(selectedDataset.created_at)}</p>
                  <p>来源：{selectedDataset.source}</p>
                </div>
              </div>
            ) : (
              <EmptyState text={datasetDetailLoading ? '正在加载数据集详情...' : '当前平台还没有可用数据集，可切换平台或稍后刷新。'} />
            )}

            <div className="space-y-2">
              {visibleSeedMetrics.map((metric) => (
                <SeedMetric
                  key={metric.key}
                  label={metric.label}
                  value={metric.value}
                  icon={metric.icon}
                  colorClass={metric.colorClass}
                />
              ))}
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
                <SelectItem value="real-seed-fusion">
                  <div className="font-bold">Real Seed Fusion</div>
                  <div className="text-[10px] text-text-muted">真实种子优先，建议作为默认策略</div>
                </SelectItem>
                <SelectItem value="persona-llm">
                  <div className="font-bold">Persona-LLM</div>
                  <div className="text-[10px] text-text-muted">强化真实用户画像与人格表达</div>
                </SelectItem>
                <SelectItem value="ba-structural">
                  <div className="font-bold">Structural Preferential Attachment</div>
                  <div className="text-[10px] text-text-muted">结构优先补边，快速补齐网络骨架</div>
                </SelectItem>
                <SelectItem value="semantic-homophily">
                  <div className="font-bold">Semantic Homophily</div>
                  <div className="text-[10px] text-text-muted">基于兴趣与文本相似度建立连接</div>
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-text-tertiary">{ALGORITHM_DESCRIPTIONS[algorithm]}</p>

            <div className="rounded-2xl border border-border-default bg-bg-primary p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-bold">当前策略输出</span>
                <Badge variant="secondary">{algorithm}</Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {ALGORITHM_OUTPUTS[algorithm].map((item) => (
                  <Badge key={item} variant="outline" className="text-[10px]">
                    {item}
                  </Badge>
                ))}
              </div>
              <p className="text-[11px] text-text-tertiary">
                算法会基于当前选中的种子数据，生成拟合用户、关系边以及最终的社交知识图谱结构。
              </p>
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xs font-bold uppercase tracking-widest text-text-tertiary">生成规模</h3>
              <span className="font-mono text-accent">{formatNumber(Number(agentCount) || 0)} Agents</span>
            </div>
            <Input
              type="number"
              min={1}
              value={agentCount}
              onChange={(event) => setAgentCount(event.target.value)}
              className="bg-bg-primary border-border-default"
            />
          </section>

          <Button
            className="w-full h-14 rounded-2xl bg-accent hover:bg-accent-hover shadow-lg shadow-accent/20 font-bold gap-2"
            onClick={handleGenerate}
            disabled={generationLoading || !selectedDatasetId}
          >
            {generationLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                进化计算中...
              </>
            ) : (
              <>
                <GitBranch className="w-4 h-4" />
                开始生成社交网络
              </>
            )}
          </Button>
        </Card>

        <div className="col-span-12 lg:col-span-8 space-y-6">
          <div className="rounded-2xl border border-accent/30 bg-accent/5 px-5 py-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-accent mb-2">3. 社交知识图谱结果</h3>
            <p className="text-sm text-text-tertiary">
              这里展示生成后的图谱结果，以及拟合用户总数、生成关系边和图密度等关键指标。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatsCard label="拟合用户总数" value={graphStats.userCount} icon={Users} />
            <StatsCard label="生成关系边" value={graphStats.linkCount} icon={Share2} />
            <StatsCard label="图密度 (Density)" value={graphStats.densityLabel} icon={Network} />
          </div>

          <Card className="bg-bg-secondary border-border-default overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex flex-col gap-3 lg:flex-row lg:justify-between lg:items-center">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary">社交知识图谱预览 (Social Knowledge Graph)</h2>
                {selectedDataset ? (
                  <p className="text-xs text-text-tertiary mt-1">
                  当前快照：{selectedDataset.dataset_id} · 采集时间 {formatBeijingTime(selectedDataset.created_at)}
                </p>
              ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedDatasetId ? <Badge variant="outline" className="text-[9px]">{selectedDatasetId}</Badge> : null}
                {currentGenerationId ? <Badge variant="secondary" className="text-[9px]">{currentGenerationId}</Badge> : null}
                <Badge variant="secondary" className="text-[9px]">Node: Agent</Badge>
                <Badge variant="outline" className="text-[9px] border-emerald-500/30 text-emerald-400">Edge: Interest</Badge>
                <Badge variant="outline" className="text-[9px] border-blue-500/30 text-blue-400">Edge: Follow</Badge>
              </div>
            </div>

            <div className="flex-1 bg-bg-primary/30 relative">
              <SocialKnowledgeGraph data={generatedGraph ? { nodes: generatedGraph.nodes, edges: generatedGraph.edges } : null} />

              {!generatedGraph && (
                <div className="absolute inset-0 flex items-center justify-center backdrop-blur-sm bg-bg-primary/40">
                  <p className="text-text-muted text-sm border border-border-default px-6 py-3 rounded-full bg-bg-secondary text-center">
                    先选择一份算法种子数据，再配置生成策略算法并生成图谱
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

function SeedMetric({
  label,
  value,
  icon: Icon,
  colorClass,
  key: _key,
}: {
  key?: string;
  label: string;
  value: number;
  icon: any;
  colorClass: string;
}) {
  return (
    <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium flex items-center gap-2">
          <Icon className={`w-4 h-4 ${colorClass}`} /> {label}
        </span>
        <Badge variant="outline" className="text-[10px]">
          {formatNumber(value)}
        </Badge>
      </div>
    </div>
  );
}

function InfoMetric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="p-3 bg-bg-primary border border-border-default rounded-xl">
      <p className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest mb-2">{label}</p>
      <p className={`text-xs text-text-primary break-all ${mono ? 'font-mono' : ''}`}>{value}</p>
    </div>
  );
}

function StatsCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: any }) {
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

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border-default bg-bg-primary/60 px-4 py-6 text-center text-sm text-text-muted">
      {text}
    </div>
  );
}
