import { type ReactNode, useEffect, useMemo, useRef, useState } from 'react'
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
  GitBranch,
  X,
  Plus,
  Loader2,
  Wand2,
  Tags,
} from 'lucide-react'
import {
  Card,
  Button,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Badge,
  Input,
} from '@/components/ui'
import { SocialKnowledgeGraph } from '@/components/SocialKnowledgeGraph'
import { SubscriptionPanel, type SubscriptionPlatformCard } from '@/components/SubscriptionPanel'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import {
  generateDatasetArtifacts,
  getGeneratedAgents,
  getPersonaDataset,
  getSocialGraphBundle,
  getTwitterSqliteTopicsList,
  listPersonaDatasets,
  postTwitterSqliteTopicsPersonasLlm,
  postTwitterSqliteTopicSeed,
  PERSONA_GENERATE_FETCH_TIMEOUT_MS,
  runSocialLocalPipeline,
  runNetworksNeo4jSync,
  type TwitterSqliteTopicOption,
} from '@/lib/personaApi'
import { buildLocalSocialGraphLayout } from '@/lib/localSocialGraphLayout'
import type {
  GeneratedAgentRecord,
  GeneratedGraphRecord,
  PersonaDatasetSummary,
} from '@/lib/personaTypes'

/** 右侧「仿真话题列表」预览项（与两阶段 LLM 返回的 topics 一致） */
type SqlitePreviewTopic = { title: string; summary: string }

type PersonaDatasetDetail = PersonaDatasetSummary & {
  latest_graph?: {
    generation_id: string
    algorithm: string
    stats: GeneratedGraphRecord['stats']
    created_at: string
  } | null
}

type SeedMetricDescriptor = {
  key: keyof typeof EMPTY_COUNTS
  label: string
  value: number
  icon: any
  colorClass: string
}

const EMPTY_COUNTS = {
  users: 0,
  posts: 0,
  replies: 0,
  relationships: 0,
  networks: 0,
  topics: 0,
}

const ALGORITHM_DESCRIPTIONS: Record<string, string> = {
  'community-homophily':
    '推荐策略：先保留真实互动边，再按话题社区、内容同质性和三角闭包补齐网络结构。',
  'real-seed-fusion': '真实种子优先，先保留已有互动与结构线索，再用最小必要补边生成稳定图谱。',
  'ba-structural': '结构优先，适合在真实关系稀疏时补出更完整的网络骨架。',
  'semantic-homophily': '基于兴趣语义相似度与真实互动边混合生成关系网络。',
}

/** 列表 API 返回的 recsys_type 大小写可能不一致，与卡片 platform.id 比较时统一为小写 */
function datasetMatchesPlatform(dataset: PersonaDatasetSummary, platformId: string) {
  return (
    String(dataset.recsys_type ?? '')
      .trim()
      .toLowerCase() === platformId.toLowerCase()
  )
}

const ALGORITHM_OUTPUTS: Record<string, string[]> = {
  'community-homophily': ['社区优先补边', '同质性约束', '三角闭包收紧结构'],
  'real-seed-fusion': ['保留真实种子结构', '最小必要补边', '稳定输出图谱'],
  'ba-structural': ['补齐关系边', '强化网络骨架', '提升连通性'],
  'semantic-homophily': ['基于兴趣连边', '混合真实互动', '优化图密度'],
}

const ALGORITHM_SEED_KEYS = {
  'community-homophily': ['users', 'posts', 'replies', 'topics'],
  'real-seed-fusion': ['users', 'posts', 'replies', 'topics'],
  'semantic-homophily': ['users', 'posts', 'replies', 'topics'],
  'ba-structural': ['users', 'posts', 'replies', 'topics', 'relationships', 'networks'],
} as const

const SEED_METRIC_META = {
  users: { label: '种子用户', icon: Users, colorClass: 'text-blue-400' },
  posts: { label: '种子帖子', icon: FileText, colorClass: 'text-rose-400' },
  replies: { label: '种子回复', icon: Activity, colorClass: 'text-emerald-400' },
  relationships: { label: '真实关系', icon: Network, colorClass: 'text-purple-400' },
  networks: { label: '网络结构', icon: Share2, colorClass: 'text-orange-400' },
  topics: { label: '话题标签', icon: Sparkles, colorClass: 'text-yellow-400' },
} as const

const PLATFORM_META = [
  { id: 'twitter', name: 'X / Twitter', colorClass: 'text-blue-400' },
  { id: 'reddit', name: 'Reddit', colorClass: 'text-orange-500' },
  { id: 'tiktok', name: '小红书', colorClass: 'text-red-500' },
  { id: 'instagram', name: 'Instagram', colorClass: 'text-purple-500' },
  { id: 'facebook', name: 'Facebook', colorClass: 'text-blue-600' },
] as const

const PLATFORM_LABELS = Object.fromEntries(
  PLATFORM_META.map(platform => [platform.id, platform.name])
) as Record<string, string>

function formatNumber(value: number | undefined | null) {
  if (value == null) return '0'
  return value.toLocaleString()
}

function formatBeijingDay(value: string | undefined | null) {
  if (!value) return '未分组'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '未分组'
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const lookup = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${lookup.year}-${lookup.month}-${lookup.day}`
}

function datasetSnapshotTimestamp(
  dataset: Pick<PersonaDatasetSummary, 'created_at' | 'updated_at'>
) {
  const createdAt = new Date(dataset.created_at).getTime()
  if (Number.isFinite(createdAt) && createdAt > 0) return createdAt
  const updatedAt = new Date(dataset.updated_at).getTime()
  return Number.isFinite(updatedAt) ? updatedAt : 0
}

function formatDensityPercent(value: number | undefined) {
  const n = Number(value)
  const v = Number.isFinite(n) ? n : 0
  return `${(v * 100).toFixed(2)}%`
}

export default function Profiles() {
  const navigate = useNavigate()

  const [selectedPlatform, setSelectedPlatform] = useState<string>('')
  const [datasets, setDatasets] = useState<PersonaDatasetSummary[]>([])
  const [selectedDatasetId, setSelectedDatasetId] = useState('')
  const [selectedDataset, setSelectedDataset] = useState<PersonaDatasetDetail | null>(null)
  const [generatedGraph, setGeneratedGraph] = useState<GeneratedGraphRecord | null>(null)
  const [currentGenerationId, setCurrentGenerationId] = useState<string | null>(null)
  /** 本次生成写入 Mongo 的拟合用户（与图谱节点一一对应，列表展示用） */
  const [generatedAgentsList, setGeneratedAgentsList] = useState<GeneratedAgentRecord[]>([])
  const [agentsListLoading, setAgentsListLoading] = useState(false)
  const [datasetDetailLoading, setDatasetDetailLoading] = useState(false)
  const [generationLoading, setGenerationLoading] = useState(false)
  const [generationElapsedSec, setGenerationElapsedSec] = useState(0)
  /** 本地 datasets/data 流水线生成的力导向图（话题圆盘 + 用户绕话题分布） */
  const [localDiskGraph, setLocalDiskGraph] = useState<{
    nodes: Record<string, unknown>[]
    edges: Record<string, unknown>[]
    fixedLayout: boolean
  } | null>(null)
  const [localDiskMetrics, setLocalDiskMetrics] = useState<{
    user_count: number
    relationship_edge_count: number
    network_density_ratio: number
  } | null>(null)
  const [subscriptionLoadingPlatform, setSubscriptionLoadingPlatform] = useState<string | null>(
    null
  )
  const platformToggleAbortRef = useRef<AbortController | null>(null)
  const [liveSubscriptions, setLiveSubscriptions] = useState<Record<string, boolean>>({
    twitter: false,
    reddit: false,
    tiktok: false,
    instagram: false,
    facebook: false,
  })
  const [algorithm, setAlgorithm] = useState('community-homophily')
  const [agentCount, setAgentCount] = useState('0')
  /** 为 true 时走 Python 子进程 + 大模型批量生成模拟 users，再构建图谱 */
  // 默认使用 LLM 生成模拟画像（不再提供开关）
  const useLlmPersonas = true

  /** SQLite 话题多选 + 合并种子统计（按当前 platform） */
  const [sqliteTopicsLoading, setSqliteTopicsLoading] = useState(false)
  const [sqliteTopicRows, setSqliteTopicRows] = useState<TwitterSqliteTopicOption[]>([])
  /** topic_key -> 是否参与合并抽样（加载后默认全为 true） */
  const [sqliteTopicSelected, setSqliteTopicSelected] = useState<Record<string, boolean>>({})
  const [sqliteSeedLoading, setSqliteSeedLoading] = useState(false)
  const [sqliteSeedCounts, setSqliteSeedCounts] = useState<{
    users: number
    posts: number
    replies: number
    topics: number
  } | null>(null)
  /** 种子用户目标人数（与选中话题下帖子/评论作者池抽样相关） */
  const [sqliteSeedUserCount, setSqliteSeedUserCount] = useState('100')
  /** 本地 LLM 画像预览，展示在右侧「拟合用户列表」（与图谱生成后的 Mongo 列表二选一优先 Mongo） */
  const [sqlitePreviewAgents, setSqlitePreviewAgents] = useState<GeneratedAgentRecord[]>([])
  /** 本地 LLM 仿真话题预览，展示在右侧「仿真话题列表」 */
  const [sqlitePreviewTopics, setSqlitePreviewTopics] = useState<SqlitePreviewTopic[]>([])
  /** 大模型先生成仿真话题再生成画像（与「仅画像」分流） */
  const [syntheticTopicCount, setSyntheticTopicCount] = useState('5')
  const [sqliteTopicsPersonasLoading, setSqliteTopicsPersonasLoading] = useState(false)

  const sqliteSelectedTopicKeys = useMemo(
    () =>
      sqliteTopicRows.filter(row => sqliteTopicSelected[row.topic_key]).map(row => row.topic_key),
    [sqliteTopicRows, sqliteTopicSelected]
  )

  const sqliteSelectedKeysSignature = useMemo(
    () => [...sqliteSelectedTopicKeys].sort().join('\0'),
    [sqliteSelectedTopicKeys]
  )

  useEffect(() => {
    setSqlitePreviewAgents([])
    setSqlitePreviewTopics([])
  }, [sqliteSelectedKeysSignature])

  const sqliteSeedUserCountParsed = useMemo(() => {
    const x = Math.floor(Number.parseInt(String(sqliteSeedUserCount).trim(), 10))
    if (!Number.isFinite(x) || x < 1) return 100
    return Math.min(2000, x)
  }, [sqliteSeedUserCount])

  const syntheticTopicCountParsed = useMemo(() => {
    const x = Math.floor(Number.parseInt(String(syntheticTopicCount).trim(), 10))
    if (!Number.isFinite(x) || x < 1) return 5
    return Math.min(64, x)
  }, [syntheticTopicCount])

  const llmUserTargetParsed = useMemo(() => {
    const x = Math.floor(Number.parseInt(String(agentCount).trim(), 10))
    if (!Number.isFinite(x) || x < 1) return 1
    return Math.min(2000, x)
  }, [agentCount])

  const displayAgentsList = useMemo(() => {
    if (generatedGraph) {
      if (agentsListLoading) return []
      if (generatedAgentsList.length > 0) return generatedAgentsList
    }
    return sqlitePreviewAgents
  }, [generatedGraph, agentsListLoading, generatedAgentsList, sqlitePreviewAgents])

  const showingSqlitePreview =
    sqlitePreviewAgents.length > 0 &&
    !(generatedGraph && !agentsListLoading && generatedAgentsList.length > 0)
  const agentsPanelBusy = agentsListLoading || sqliteTopicsPersonasLoading

  const platformSubscribed = Boolean(selectedPlatform && liveSubscriptions[selectedPlatform])

  const platformDatasets = useMemo(
    () =>
      datasets
        .filter(dataset => datasetMatchesPlatform(dataset, selectedPlatform))
        .sort((left, right) => datasetSnapshotTimestamp(right) - datasetSnapshotTimestamp(left)),
    [datasets, selectedPlatform]
  )

  const graphStats = useMemo(() => {
    if (localDiskMetrics) {
      return {
        userCount: localDiskMetrics.user_count,
        linkCount: localDiskMetrics.relationship_edge_count,
        densityLabel: formatDensityPercent(localDiskMetrics.network_density_ratio),
      }
    }
    if (generatedGraph?.stats) {
      const s = generatedGraph.stats
      return {
        userCount: s.agentCount || 0,
        linkCount: s.edgeCount || 0,
        densityLabel: formatDensityPercent(s.density),
      }
    }
    const previewN = sqlitePreviewAgents.length
    return {
      userCount: previewN,
      linkCount: 0,
      densityLabel: formatDensityPercent(undefined),
    }
  }, [generatedGraph, sqlitePreviewAgents.length, localDiskMetrics])

  const mongoCounts = selectedDataset?.counts || EMPTY_COUNTS
  const effectiveSeedCounts = useMemo(() => {
    let base = mongoCounts
    if (sqliteSelectedTopicKeys.length > 0 && sqliteSeedCounts) {
      base = {
        ...mongoCounts,
        users: sqliteSeedCounts.users,
        posts: sqliteSeedCounts.posts,
        replies: sqliteSeedCounts.replies,
        topics: sqliteSeedCounts.topics,
      }
    }
    if (sqlitePreviewAgents.length > 0) {
      return { ...base, users: sqlitePreviewAgents.length }
    }
    return base
  }, [mongoCounts, sqliteSeedCounts, sqliteSelectedKeysSignature, sqlitePreviewAgents.length])

  const visibleSeedMetrics = useMemo<SeedMetricDescriptor[]>(() => {
    const keys = ALGORITHM_SEED_KEYS[algorithm as keyof typeof ALGORITHM_SEED_KEYS]
    return keys.map((key: keyof typeof SEED_METRIC_META) => ({
      key,
      ...SEED_METRIC_META[key],
      value: effectiveSeedCounts[key],
    }))
  }, [algorithm, effectiveSeedCounts])

  const platformCards = useMemo<SubscriptionPlatformCard[]>(
    () =>
      PLATFORM_META.map(platform => {
        const platformItems = datasets
          .filter(dataset => datasetMatchesPlatform(dataset, platform.id))
          .sort((left, right) => datasetSnapshotTimestamp(right) - datasetSnapshotTimestamp(left))
        const datasetCount = platformItems.length
        const dayCount = new Set(platformItems.map(dataset => formatBeijingDay(dataset.created_at)))
          .size
        const checked = liveSubscriptions[platform.id]

        return {
          id: platform.id,
          name: platform.name,
          status:
            subscriptionLoadingPlatform === platform.id
              ? 'syncing'
              : checked
                ? 'connected'
                : 'standby',
          progress: subscriptionLoadingPlatform === platform.id ? 65 : checked ? 100 : 0,
          checked,
          canToggle: true,
          datasets: datasetCount,
          note:
            subscriptionLoadingPlatform === platform.id
              ? '正在读取可用数据集。'
              : datasetCount > 0
                ? `已发现 ${datasetCount} 份快照，覆盖 ${dayCount} 天。`
                : '暂未发现可用数据集。',
          colorClass: platform.colorClass,
        }
      }),
    [datasets, liveSubscriptions, subscriptionLoadingPlatform]
  )

  const loadDatasets = async (preferredDatasetId?: string) => {
    try {
      const { datasets: items } = await listPersonaDatasets({
        signal: platformToggleAbortRef.current?.signal,
      })
      setDatasets(items)

      if (preferredDatasetId) {
        setSelectedDatasetId(preferredDatasetId)
      }
      return items
    } catch (error) {
      console.error('Load datasets error:', error)
      // Socitwin 默认不启用 Mongo：列表为空属正常，不弹错误打扰
      setDatasets([])
      return [] as PersonaDatasetSummary[]
    }
  }

  const loadDatasetDetail = async (datasetId: string) => {
    if (!datasetId) {
      setSelectedDataset(null)
      setGeneratedGraph(null)
      setCurrentGenerationId(null)
      return
    }

    setDatasetDetailLoading(true)
    setGeneratedGraph(null)
    setCurrentGenerationId(null)
    try {
      const { dataset } = await getPersonaDataset(datasetId)
      const detail = dataset as PersonaDatasetDetail
      setSelectedDataset(detail)
    } catch (error) {
      console.error('Load dataset detail error:', error)
      toast.error('加载数据集详情失败')
      setSelectedDataset(null)
      setGeneratedGraph(null)
      setCurrentGenerationId(null)
    } finally {
      setDatasetDetailLoading(false)
    }
  }

  useEffect(() => {
    if (!liveSubscriptions[selectedPlatform]) {
      if (selectedDatasetId) setSelectedDatasetId('')
      setSelectedDataset(null)
      setGeneratedGraph(null)
      setCurrentGenerationId(null)
      return
    }

    if (!platformDatasets.length) {
      if (selectedDatasetId) setSelectedDatasetId('')
      return
    }
  }, [liveSubscriptions, platformDatasets.length, selectedPlatform, selectedDatasetId])

  useEffect(() => {
    if (!liveSubscriptions[selectedPlatform]) return
    if (!platformDatasets.length) {
      if (selectedDatasetId) setSelectedDatasetId('')
      return
    }
    if (!platformDatasets.some(dataset => dataset.dataset_id === selectedDatasetId)) {
      setSelectedDatasetId(platformDatasets[0].dataset_id)
    }
  }, [platformDatasets, liveSubscriptions, selectedDatasetId, selectedPlatform])

  useEffect(() => {
    loadDatasetDetail(selectedDatasetId).catch(() => {
      // Error handled in loadDatasetDetail.
    })
  }, [selectedDatasetId])

  useEffect(() => {
    setGeneratedAgentsList([])
    setCurrentGenerationId(null)
    setGeneratedGraph(null)
  }, [selectedDatasetId])

  useEffect(() => {
    setSqliteTopicRows([])
    setSqliteTopicSelected({})
    setSqliteSeedCounts(null)
    setSqliteSeedUserCount('100')
    setSqlitePreviewAgents([])
    setSqlitePreviewTopics([])
    setSyntheticTopicCount('5')
  }, [selectedPlatform])

  useEffect(() => {
    if (!selectedPlatform || !liveSubscriptions[selectedPlatform]) {
      setSqliteTopicsLoading(false)
      return
    }
    let cancelled = false
    setSqliteTopicsLoading(true)
    void getTwitterSqliteTopicsList({ recentPool: 2000, platform: selectedPlatform })
      .then(res => {
        if (cancelled) return
        const rows = res.topics
        setSqliteTopicRows(rows)
        const nextSel: Record<string, boolean> = {}
        for (const row of rows) nextSel[row.topic_key] = true
        setSqliteTopicSelected(nextSel)
      })
      .catch(error => {
        if (!cancelled) {
          console.error('SQLite topics:', error)
          toast.error((error as Error).message || '加载 SQLite 话题失败')
          setSqliteTopicRows([])
          setSqliteTopicSelected({})
        }
      })
      .finally(() => {
        if (!cancelled) setSqliteTopicsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedPlatform, liveSubscriptions])

  useEffect(() => {
    if (
      !selectedPlatform ||
      !liveSubscriptions[selectedPlatform] ||
      sqliteSelectedTopicKeys.length === 0
    ) {
      setSqliteSeedCounts(null)
      return
    }
    let cancelled = false
    setSqliteSeedLoading(true)
    void postTwitterSqliteTopicSeed(
      sqliteSelectedTopicKeys,
      sqliteSeedUserCountParsed,
      selectedPlatform
    )
      .then(res => {
        if (cancelled) return
        setSqliteSeedCounts(res.counts)
      })
      .catch(error => {
        if (!cancelled) {
          console.error('SQLite topic seed:', error)
          toast.error((error as Error).message || '加载话题种子统计失败')
          setSqliteSeedCounts(null)
        }
      })
      .finally(() => {
        if (!cancelled) setSqliteSeedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedPlatform, liveSubscriptions, sqliteSelectedKeysSignature, sqliteSeedUserCountParsed])

  useEffect(() => {
    const users = selectedDataset?.counts?.users
    if (users != null && users > 0) {
      setAgentCount(String(users))
      return
    }
    setAgentCount(prev => {
      const n = Number.parseInt(String(prev).trim(), 10)
      return Number.isFinite(n) && n > 0 ? prev : '10'
    })
  }, [selectedDataset?.counts?.users])

  const handleSqliteTopicsPersonasLlm = async () => {
    if (!selectedPlatform || !liveSubscriptions[selectedPlatform]) {
      toast.error('请先订阅当前平台')
      return
    }
    if (sqliteSelectedTopicKeys.length === 0) {
      toast.error('请先勾选至少一个话题')
      return
    }
    setSqliteTopicsPersonasLoading(true)
    setSqlitePreviewAgents([])
    setSqlitePreviewTopics([])
    try {
      toast.info(
        `将先根据已选话题用大模型生成 ${syntheticTopicCountParsed} 条仿真话题，再结合种子用户生成 ${llmUserTargetParsed} 条画像。`
      )
      const res = await postTwitterSqliteTopicsPersonasLlm({
        topic_keys: sqliteSelectedTopicKeys,
        seed_user_count: sqliteSeedUserCountParsed,
        synthetic_topic_count: syntheticTopicCountParsed,
        user_target_count: llmUserTargetParsed,
        platform: selectedPlatform,
        llmBatchSize: 15,
        llmSeedSample: 10,
        llmMaxRetries: 5,
        llmKolNormalRatio: '1:10',
      })
      setSqlitePreviewAgents(
        (res.users ?? []).map((u, idx) =>
          mapSqliteLlmUserToAgent(
            u as Record<string, unknown>,
            idx,
            res.dataset_id,
            'topics_personas'
          )
        )
      )
      setSqlitePreviewTopics(
        (res.topics ?? []).map(t => ({
          title: String(t.title ?? '').trim() || '（无标题）',
          summary: String(t.summary ?? '').trim(),
        }))
      )
      const nUsers = res.users?.length ?? 0
      if (nUsers > 0) {
        setAgentCount(String(nUsers))
      }
      const p = res.sqlite_persist
      toast.success('用户画像和话题数据已生成')
      if (p?.ok === false) {
        toast.error(`SQLite 写入失败：${p.error ?? '未知错误'}`)
      }
    } catch (error) {
      console.error('SQLite topics+personas LLM:', error)
      toast.error((error as Error).message || '仿真话题与用户画像生成失败')
    } finally {
      setSqliteTopicsPersonasLoading(false)
    }
  }

  const handleTogglePlatform = async (platformId: string, checked: boolean) => {
    const platformName = PLATFORM_LABELS[platformId] || platformId
    if (checked) {
      const onlyThis =
        liveSubscriptions[platformId] &&
        Object.values(liveSubscriptions).filter(Boolean).length === 1
      if (onlyThis) {
        setSelectedPlatform(platformId)
        return
      }
    }
    if (!checked) {
      setLiveSubscriptions({
        twitter: false,
        reddit: false,
        tiktok: false,
        instagram: false,
        facebook: false,
      })
      setSelectedPlatform('')
      setSelectedDatasetId('')
      setSelectedDataset(null)
      setGeneratedGraph(null)
      setCurrentGenerationId(null)
      toast.success(`已取消 ${platformName} 数据集订阅视图`)
      return
    }

    platformToggleAbortRef.current?.abort()
    platformToggleAbortRef.current = new AbortController()

    setSubscriptionLoadingPlatform(platformId)
    try {
      setSelectedPlatform(platformId)
      setSelectedDatasetId('')
      setSelectedDataset(null)
      setGeneratedGraph(null)
      setCurrentGenerationId(null)
      const items = await loadDatasets()
      if (platformToggleAbortRef.current.signal.aborted) return
      const subscribedDatasets = items
        .filter(dataset => datasetMatchesPlatform(dataset, platformId))
        .sort((left, right) => datasetSnapshotTimestamp(right) - datasetSnapshotTimestamp(left))
      setLiveSubscriptions({
        twitter: false,
        reddit: false,
        tiktok: false,
        instagram: false,
        facebook: false,
        [platformId]: true,
      })
      if (subscribedDatasets[0]?.dataset_id) {
        setSelectedDatasetId(subscribedDatasets[0].dataset_id)
      } else {
        setSelectedDatasetId('')
        setSelectedDataset(null)
        setGeneratedGraph(null)
        setCurrentGenerationId(null)
      }

      try {
        const topicRes = await getTwitterSqliteTopicsList({
          recentPool: 2000,
          platform: platformId,
          signal: platformToggleAbortRef.current?.signal,
        })
        if (platformToggleAbortRef.current.signal.aborted) return
        const n = topicRes.topics.length
        if (subscribedDatasets[0]?.dataset_id) {
          toast.success(
            `已载入 ${subscribedDatasets.length} 份 ${platformName} 数据集；SQLite 话题 ${n} 条`
          )
        } else if (n > 0) {
          toast.success(`已从本地库加载 ${n} 条 ${platformName} 话题（datasets 列表可为空）`)
        } else {
          toast.info(
            `${platformName}：datasets 列表与 topics 均未发现数据，请检查 oasis_datasets.db 中 platform 字段是否一致`
          )
        }
      } catch (e) {
        if ((e as Error)?.name === 'AbortError') return
        console.error('SQLite topics (toast):', e)
        toast.error((e as Error).message || '读取本地话题失败')
      }
    } catch (error) {
      if ((error as Error)?.name === 'AbortError') return
      console.error('Load platform datasets error:', error)
      setLiveSubscriptions({
        twitter: false,
        reddit: false,
        tiktok: false,
        instagram: false,
        facebook: false,
      })
      setSelectedPlatform('')
      toast.error((error as Error).message || '载入数据集失败')
    } finally {
      if (!platformToggleAbortRef.current?.signal.aborted) {
        setSubscriptionLoadingPlatform(null)
      }
    }
  }

  useEffect(() => {
    if (!generationLoading) {
      setGenerationElapsedSec(0)
      return
    }
    const t0 = Date.now()
    const id = window.setInterval(() => {
      setGenerationElapsedSec(Math.floor((Date.now() - t0) / 1000))
    }, 1000)
    return () => window.clearInterval(id)
  }, [generationLoading])

  const graphDisplayData = useMemo(() => {
    if (localDiskGraph) {
      return {
        nodes: localDiskGraph.nodes,
        edges: localDiskGraph.edges,
        fixedLayout: localDiskGraph.fixedLayout,
      }
    }
    if (generatedGraph) {
      return { nodes: generatedGraph.nodes, edges: generatedGraph.edges }
    }
    return null
  }, [localDiskGraph, generatedGraph])

  const clearGeneratedGraphState = () => {
    setGeneratedGraph(null)
    setCurrentGenerationId(null)
    setGeneratedAgentsList([])
  }

  const clearLocalGraphState = () => {
    setLocalDiskGraph(null)
    setLocalDiskMetrics(null)
  }

  const isAbortLikeError = (err: Error & { name?: string }) =>
    err?.name === 'AbortError' ||
    (typeof err?.message === 'string' &&
      (err.message.includes('aborted') || err.message.includes('signal is aborted')))

  const runNeo4jSyncBestEffort = async () => {
    try {
      toast.info('正在将 users/topics/relationships/user_networks 同步到 Neo4j…')
      await runNetworksNeo4jSync()
      toast.success('Neo4j 知识图谱已同步')
    } catch (neoErr) {
      console.error('Neo4j sync:', neoErr)
      toast.warning((neoErr as Error)?.message || 'Neo4j 同步失败')
    }
  }

  const generateTwitterLocalGraph = async () => {
    toast.info('正在生成社交网络…')
    try {
      await runSocialLocalPipeline()
      const bundle = await getSocialGraphBundle()
      const laid = buildLocalSocialGraphLayout(bundle)
      setLocalDiskGraph({ nodes: laid.nodes, edges: laid.edges, fixedLayout: laid.fixedLayout })
      const m = bundle.metrics || {}
      setLocalDiskMetrics({
        user_count: Number(m.user_count) || 0,
        relationship_edge_count: Number(m.relationship_edge_count) || 0,
        network_density_ratio: Number(m.network_density_ratio) || 0,
      })
      clearGeneratedGraphState()
      if (selectedDatasetId) {
        await loadDatasets(selectedDatasetId)
      }
      toast.success('旧版社交关系已生成：已更新关系边、图密度与社交知识图谱')
      await runNeo4jSyncBestEffort()
    } catch (pipeErr) {
      console.error('Social pipeline / graph bundle:', pipeErr)
      toast.warning(
        (pipeErr as Error)?.message?.includes('501')
          ? '后端未接入旧版 datasets 流水线（501），已跳过关系图生成；左侧拟合用户与 LLM 结果仍可用。'
          : (pipeErr as Error)?.message || '关系图生成失败（可能未部署本地流水线）'
      )
    }
  }

  const generateDatasetGraph = async () => {
    clearLocalGraphState()
    const minWait = Math.ceil(PERSONA_GENERATE_FETCH_TIMEOUT_MS / 60_000)
    toast.info(
      `将使用大模型生成模拟画像：需多次调用模型，人数较多时可能需数分钟；按钮上会显示已等待时间。若超过约 ${minWait} 分钟仍无结果，前端会主动超时并提示。`
    )
    const result = await generateDatasetArtifacts(selectedDatasetId, {
      algorithm,
      agentCount: Math.max(1, llmUserTargetParsed || selectedDataset?.counts.users || 1),
      useLlmPersonas,
      // 默认更稳的参数：减小单次返回 JSON 的长度，降低网关/模型超时概率
      llmBatchSize: 15,
      llmSeedSample: 10,
      llmMaxRetries: 5,
      llmKolNormalRatio: '1:10',
    })
    setGeneratedGraph(result.graph)
    setCurrentGenerationId(result.generation_id)
    setSqlitePreviewAgents([])
    setSqlitePreviewTopics([])
    setAgentsListLoading(true)
    try {
      const agentsRes = await getGeneratedAgents(result.generation_id)
      setGeneratedAgentsList(agentsRes.agents)
    } catch (e) {
      console.error('Load generated agents list:', e)
      setGeneratedAgentsList([])
      toast.message('图谱已生成，但拟合用户列表加载失败，可在图谱悬停节点查看单点信息。')
    } finally {
      setAgentsListLoading(false)
    }
    await loadDatasets(selectedDatasetId)
    toast.success(`已基于 ${selectedDatasetId} 生成社交网络`)
  }

  const handleGenerate = async () => {
    setGenerationLoading(true)
    try {
      // 默认：点击即执行旧版本地流水线（topics_classify → users_format_convert → relations_generate）
      // 输出 relationships.json / user_networks.json / users.json / topics.json / graph_metrics.json，
      // 前端再读取并生成「话题盘 + 话题内用户盘」社交知识图谱。
      await generateTwitterLocalGraph()
    } catch (error) {
      console.error('Generation error:', error)
      const err = error as Error & { name?: string }
      if (isAbortLikeError(err)) {
        const min = Math.round(PERSONA_GENERATE_FETCH_TIMEOUT_MS / 60_000)
        toast.error(
          `生成请求已超时（前端等待超过 ${min} 分钟）。可尝试减小生成规模、检查大模型服务与网络，或在 .env 中增大 VITE_PERSONA_GENERATE_TIMEOUT_MS（需与后端 OASIS_LLM_PERSONA_TIMEOUT_MS 等配置协调）。`
        )
      } else {
        toast.error(err.message || '生成社交网络失败')
      }
    } finally {
      setGenerationLoading(false)
    }
  }

  return (
    <div className="px-6 lg:px-12 py-12 space-y-8">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <BrainCircuit className="w-10 h-10 text-accent" />
            仿真画像实验室
          </h1>
          <p className="text-text-tertiary mt-1">
            选择算法种子数据，配置生成策略算法，输出社交知识图谱与关键指标
          </p>
        </div>
        {(generatedGraph || localDiskGraph) && (
          <Button
            variant="outline"
            className="rounded-xl border-accent text-accent h-10 gap-2"
            onClick={() => navigate('/overview')}
          >
            <PlayCircle className="w-4 h-4" />
            应用并启动仿真
          </Button>
        )}
      </header>

      <SubscriptionPanel
        platforms={platformCards}
        selectedPlatform={selectedPlatform}
        onSelectPlatform={platformId => {
          if (liveSubscriptions[platformId]) {
            setSelectedPlatform(platformId)
          }
        }}
        onTogglePlatform={(platformId, checked) => {
          void handleTogglePlatform(platformId, checked)
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
                <span className="text-sm font-bold">
                  当前平台：{PLATFORM_LABELS[selectedPlatform] || selectedPlatform || '未选择'}
                </span>
                <Badge variant="outline" className="shrink-0 text-[10px] tabular-nums">
                  {sqliteTopicsLoading ? 'SQLite · …' : `SQLite · ${sqliteTopicRows.length} 话题`}
                </Badge>
              </div>
            </div>

            {!platformSubscribed ? (
              <p className="text-[11px] text-text-muted leading-relaxed">
                请先在上方「全网数据实时订阅」中开启对应平台的开关，再加载该平台 SQLite 话题与种子。
              </p>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">
                    话题列表（按话题下帖子与评论作者）
                  </label>
                  <Badge variant="outline" className="shrink-0 text-[10px] tabular-nums">
                    已选 {sqliteSelectedTopicKeys.length}/{sqliteTopicRows.length}
                  </Badge>
                </div>
                <div className="max-h-[min(40vh,280px)] overflow-y-auto overscroll-y-contain rounded-xl border border-border-default bg-bg-primary shadow-inner">
                  {sqliteTopicsLoading ? (
                    <p className="p-4 text-xs text-text-muted">话题加载中…</p>
                  ) : sqliteTopicRows.length === 0 ? (
                    <p className="p-4 text-xs leading-relaxed text-text-muted">暂无话题。</p>
                  ) : (
                    <ul className="divide-y divide-border-default">
                      {sqliteTopicRows.map(row => {
                        const on = Boolean(sqliteTopicSelected[row.topic_key])
                        return (
                          <li
                            key={row.topic_key}
                            className={`flex items-start gap-2 px-3 py-2.5 transition-colors ${
                              on ? 'bg-accent/5' : 'bg-bg-primary/40 opacity-75'
                            }`}
                          >
                            <p className="min-w-0 flex-1 text-xs leading-snug text-text-secondary">
                              {row.topic_label}
                            </p>
                            {on ? (
                              <button
                                type="button"
                                aria-label="取消选择该话题"
                                className="shrink-0 rounded-lg p-1.5 text-text-muted transition-colors hover:bg-rose-500/10 hover:text-rose-400"
                                onClick={() =>
                                  setSqliteTopicSelected(prev => ({
                                    ...prev,
                                    [row.topic_key]: false,
                                  }))
                                }
                              >
                                <X className="h-4 w-4" />
                              </button>
                            ) : (
                              <button
                                type="button"
                                aria-label="重新选择该话题"
                                className="shrink-0 rounded-lg p-1.5 text-accent transition-colors hover:bg-accent/10"
                                onClick={() =>
                                  setSqliteTopicSelected(prev => ({
                                    ...prev,
                                    [row.topic_key]: true,
                                  }))
                                }
                              >
                                <Plus className="h-4 w-4" />
                              </button>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">
                    种子用户目标人数
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={2000}
                    value={sqliteSeedUserCount}
                    onChange={e => setSqliteSeedUserCount(e.target.value)}
                    className="h-11 rounded-xl border-border-default bg-bg-primary font-mono text-sm"
                  />
                </div>
                {sqliteSeedLoading ? (
                  <p className="text-[11px] text-text-muted">正在按帖子/评论池计算种子…</p>
                ) : null}
              </div>
            )}

            {!selectedDataset && platformSubscribed ? (
              <p className="text-[11px] text-text-muted leading-relaxed">
                {datasetDetailLoading
                  ? '正在加载数据集详情…'
                  : '若列表侧暂无数据集元数据，仍可依据上方 SQLite 话题与种子统计操作；生成社交网络时会优先使用当前平台已订阅的数据集 ID（若有）。'}
              </p>
            ) : null}

            <div className="space-y-2">
              {visibleSeedMetrics.map(metric => (
                <div key={metric.key}>
                  <SeedMetric
                    label={metric.label}
                    value={metric.value}
                    icon={metric.icon}
                    colorClass={metric.colorClass}
                  />
                </div>
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
                <SelectItem value="community-homophily">
                  <div className="font-bold">Community Homophily</div>
                  <div className="text-[10px] text-text-muted">
                    推荐默认策略，社区结构 + 同质性 + 三角闭包
                  </div>
                </SelectItem>
                <SelectItem value="real-seed-fusion">
                  <div className="font-bold">Real Seed Fusion</div>
                  <div className="text-[10px] text-text-muted">
                    旧版稳健策略，真实边优先后做少量补边
                  </div>
                </SelectItem>
                <SelectItem value="ba-structural">
                  <div className="font-bold">Structural Preferential Attachment</div>
                  <div className="text-[10px] text-text-muted">
                    实验策略，按结构优先快速补齐网络骨架
                  </div>
                </SelectItem>
                <SelectItem value="semantic-homophily">
                  <div className="font-bold">Semantic Homophily</div>
                  <div className="text-[10px] text-text-muted">
                    实验策略，按兴趣与文本相似度连边
                  </div>
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
                {ALGORITHM_OUTPUTS[algorithm].map(item => (
                  <Badge key={item} variant="outline" className="text-[10px]">
                    {item}
                  </Badge>
                ))}
              </div>
              <p className="text-[11px] text-text-tertiary">
                算法会基于当前选中的种子数据，生成拟合用户、关系边以及最终的社交知识图谱结构。
              </p>
              {selectedDataset?.latest_generation_id ? (
                <p className="text-[11px] text-text-muted">
                  当前数据集已有历史生成结果，但不会自动加载；点击“开始生成社交网络”后会按当前算法重新生成。
                </p>
              ) : null}
            </div>
          </section>

          <section className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                生成规模
              </h3>
              <span className="font-mono text-accent">
                {formatNumber(llmUserTargetParsed)} Agents
              </span>
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">
                大模型拟生成用户数
              </label>
              <Input
                type="number"
                min={1}
                max={2000}
                value={agentCount}
                onChange={event => setAgentCount(event.target.value)}
                className="bg-bg-primary border-border-default h-11 rounded-xl font-mono text-sm"
              />
            </div>
            {platformSubscribed ? (
              <>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold uppercase tracking-widest text-text-tertiary">
                    仿真话题数量（LLM）
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={64}
                    value={syntheticTopicCount}
                    onChange={e => setSyntheticTopicCount(e.target.value)}
                    className="bg-bg-primary border-border-default h-11 rounded-xl font-mono text-sm"
                  />
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  className="w-full h-11 rounded-xl border border-accent/30 font-semibold"
                  disabled={
                    sqliteTopicsPersonasLoading ||
                    sqliteSeedLoading ||
                    sqliteTopicsLoading ||
                    sqliteSelectedTopicKeys.length === 0
                  }
                  onClick={() => void handleSqliteTopicsPersonasLlm()}
                >
                  {sqliteTopicsPersonasLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      正在生成仿真话题与画像…
                    </>
                  ) : (
                    <>
                      <Wand2 className="mr-2 h-4 w-4" />
                      生成仿真话题与用户画像
                    </>
                  )}
                </Button>
              </>
            ) : null}
          </section>

          <Button
            className="w-full h-14 rounded-2xl bg-accent hover:bg-accent-hover shadow-lg shadow-accent/20 font-bold gap-2"
            onClick={handleGenerate}
            disabled={generationLoading || (!selectedDatasetId && sqlitePreviewAgents.length === 0)}
          >
            {generationLoading ? (
              <>
                <div className="w-4 h-4 border-2 border-bg-primary border-t-transparent rounded-full animate-spin" />
                进化计算中…
                <span className="font-mono text-xs opacity-90 tabular-nums">
                  {Math.floor(generationElapsedSec / 60)}:
                  {String(generationElapsedSec % 60).padStart(2, '0')}
                </span>
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
            <h3 className="text-xs font-bold uppercase tracking-widest text-accent mb-2">
              3. 社交知识图谱结果
            </h3>
            <p className="text-sm text-text-tertiary">
              这里展示生成后的图谱结果，以及拟合用户总数、生成关系边和图密度等关键指标。
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatsCard label="拟合用户总数" value={graphStats.userCount} icon={Users} />
            <StatsCard label="生成关系边" value={graphStats.linkCount} icon={Share2} />
            <StatsCard label="图密度 (Density)" value={graphStats.densityLabel} icon={Network} />
          </div>

          <Card className="bg-bg-secondary border-border-default p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold uppercase tracking-widest text-accent flex items-center gap-2">
                <Tags className="w-4 h-4" />
                仿真话题列表
              </h3>
              <Badge variant="outline" className="text-[9px]">
                {sqliteTopicsPersonasLoading && sqlitePreviewTopics.length === 0
                  ? '生成中…'
                  : `${sqlitePreviewTopics.length} 条`}
              </Badge>
            </div>
            {sqliteTopicsPersonasLoading && sqlitePreviewTopics.length === 0 ? (
              <p className="text-sm text-text-muted">正在生成仿真话题…</p>
            ) : sqlitePreviewTopics.length === 0 ? null : (
              <div className="max-h-[min(320px,40vh)] space-y-2 overflow-y-auto pr-1">
                {sqlitePreviewTopics.map((topic, idx) => (
                  <div
                    key={`sqlite-topic-preview-${idx}`}
                    className="rounded-xl border border-border-default bg-bg-primary/80 p-3 text-left"
                  >
                    <div className="font-bold text-sm text-text-primary leading-snug">
                      {topic.title}
                    </div>
                    {topic.summary ? (
                      <p className="mt-1.5 text-[11px] text-text-tertiary leading-snug line-clamp-3">
                        {topic.summary}
                      </p>
                    ) : (
                      <p className="mt-1.5 text-[11px] text-text-muted">—</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="bg-bg-secondary border-border-default p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-bold uppercase tracking-widest text-accent flex items-center gap-2">
                <Users className="w-4 h-4" />
                拟合用户列表
              </h3>
              <Badge variant="outline" className="text-[9px]">
                {agentsPanelBusy && displayAgentsList.length === 0
                  ? sqliteTopicsPersonasLoading
                    ? '生成中…'
                    : '加载中…'
                  : `${displayAgentsList.length} 人`}
              </Badge>
            </div>
            {agentsPanelBusy && displayAgentsList.length === 0 ? (
              <p className="text-sm text-text-muted">
                {sqliteTopicsPersonasLoading ? '正在调用大模型生成用户画像…' : '正在加载用户列表…'}
              </p>
            ) : displayAgentsList.length === 0 ? null : (
              <div className="max-h-[min(420px,50vh)] space-y-2 overflow-y-auto pr-1">
                {displayAgentsList.map(agent => (
                  <div
                    key={
                      showingSqlitePreview
                        ? `sqlite-llm-${agent.dataset_id}-${agent.generated_agent_id}`
                        : `${agent.generation_id}-${agent.generated_agent_id}`
                    }
                    className="rounded-xl border border-border-default bg-bg-primary/80 p-3 text-left"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="font-bold text-sm text-text-primary">{agent.name}</span>
                      <span className="font-mono text-[10px] text-text-muted">
                        @{agent.user_name}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-text-tertiary line-clamp-2">
                      {agent.description || agent.profile?.other_info?.user_profile || '—'}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(agent.interests?.length
                        ? agent.interests
                        : agent.profile?.other_info?.topics || []
                      )
                        .slice(0, 8)
                        .map(t => (
                          <Badge key={t} variant="secondary" className="text-[8px] font-normal">
                            {t}
                          </Badge>
                        ))}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-2 text-[9px] text-text-muted">
                      {agent.user_type ? <span>类型 {agent.user_type}</span> : null}
                      {agent.profile?.other_info?.country ? (
                        <span>{String(agent.profile.other_info.country)}</span>
                      ) : null}
                      {agent.profile?.other_info?.gender != null ? (
                        <span>{String(agent.profile.other_info.gender)}</span>
                      ) : null}
                      {agent.profile?.other_info?.age != null ? (
                        <span>{String(agent.profile.other_info.age)} 岁</span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card className="bg-bg-secondary border-border-default p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                图谱元素说明
              </h3>
              <Badge variant="secondary" className="text-[9px]">
                点击生成后展示
              </Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm text-text-tertiary">
              <GraphLegendItem
                swatch={
                  <span className="inline-flex h-3 w-3 rounded-full border border-sky-400 bg-sky-500/80" />
                }
                title="蓝色圆点"
                description="生成后的用户节点，每个节点对应一个 agent；同类节点现在统一大小和颜色。"
              />
              <GraphLegendItem
                swatch={
                  <span className="inline-flex h-3 w-3 rotate-45 border border-rose-400 bg-rose-500/80" />
                }
                title="红色方块"
                description="话题节点，表示当前图谱中的高频 topic，会比用户节点略大一些。"
              />
              <GraphLegendItem
                swatch={<span className="inline-flex h-[2px] w-8 rounded bg-sky-400" />}
                title="蓝色实线"
                description="真实边，来自 reply、mention、relationship、network 等真实互动。"
              />
              <GraphLegendItem
                swatch={
                  <span className="inline-flex h-[2px] w-8 border-t-2 border-dashed border-amber-400" />
                }
                title="黄色虚线"
                description="孤立或弱连接用户与网络枢纽（优先 KOL）的示意连线，便于在图中看见与主干社交网的衔接。"
              />
              <GraphLegendItem
                swatch={<span className="inline-flex h-[2px] w-8 rounded bg-rose-400" />}
                title="红色连线"
                description="话题归属边，表示某个用户节点与 topic node 的关联。"
              />
            </div>
          </Card>

          <Card className="bg-bg-secondary border-border-default overflow-hidden flex flex-col h-[600px]">
            <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex flex-col gap-3 lg:flex-row lg:justify-between lg:items-center">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary">
                  社交知识图谱预览 (Social Knowledge Graph)
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedDatasetId ? (
                  <Badge variant="outline" className="text-[9px]">
                    {selectedDatasetId}
                  </Badge>
                ) : null}
                {currentGenerationId ? (
                  <Badge variant="secondary" className="text-[9px]">
                    {currentGenerationId}
                  </Badge>
                ) : null}
                <Badge variant="secondary" className="text-[9px]">
                  Node: Agent / Topic
                </Badge>
                <Badge variant="outline" className="text-[9px] border-sky-500/30 text-sky-400">
                  Edge: Real
                </Badge>
                <Badge variant="outline" className="text-[9px] border-amber-500/30 text-amber-400">
                  Edge: Synthetic
                </Badge>
              </div>
            </div>

            <div className="flex-1 bg-bg-primary/30 relative">
              <SocialKnowledgeGraph data={graphDisplayData} />

              {!graphDisplayData && (
                <div className="absolute inset-0 flex items-center justify-center backdrop-blur-sm bg-bg-primary/40">
                  <p className="text-text-muted text-sm border border-border-default px-6 py-3 rounded-full bg-bg-secondary text-center">
                    选择种子数据后，点击“开始生成社交网络”才会生成并展示图谱
                  </p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}

/** 将 SQLite LLM 返回的 user 文档映射为与图谱列表一致的 GeneratedAgentRecord（仅前端预览）。 */
function mapSqliteLlmUserToAgent(
  row: Record<string, unknown>,
  idx: number,
  datasetId: string,
  kind: 'personas' | 'topics_personas'
): GeneratedAgentRecord {
  const prof =
    typeof row.profile === 'object' && row.profile !== null
      ? (row.profile as GeneratedAgentRecord['profile'])
      : undefined
  const rawOi = prof?.other_info as
    | (GeneratedAgentRecord['profile']['other_info'] & { user_type?: string })
    | undefined
  const oi = rawOi ?? {
    user_profile: '',
    topics: [] as string[],
    gender: null,
    age: null,
    mbti: null,
    country: null,
  }
  const topics = Array.isArray(oi.topics) ? oi.topics.map(t => String(t)) : []
  const ageRaw = oi.age
  let age: number | null = null
  if (typeof ageRaw === 'number' && Number.isFinite(ageRaw)) {
    age = Math.round(ageRaw)
  } else if (typeof ageRaw === 'string' && /^\d+$/.test(ageRaw)) {
    age = Number(ageRaw)
  }

  return {
    generation_id: `sqlite_llm_${kind}`,
    dataset_id: String(row.dataset_id ?? datasetId),
    algorithm: kind,
    generated_agent_id: idx + 1,
    source_user_key: String(row.twitter_user_id ?? row.user_name ?? idx),
    user_name: String(row.user_name ?? ''),
    name: String(row.name ?? ''),
    description: String(row.description ?? ''),
    profile: {
      other_info: {
        user_profile: String(oi.user_profile ?? ''),
        topics,
        gender: oi.gender != null ? String(oi.gender) : null,
        age,
        mbti: oi.mbti != null ? String(oi.mbti) : null,
        country: oi.country != null ? String(oi.country) : null,
      },
    },
    recsys_type: String(row.recsys_type ?? 'twitter'),
    user_type: String(rawOi?.user_type ?? 'normal'),
    interests: topics,
    metadata: {},
    created_at: '',
  }
}

/** 列表项请在外层写 key={...}；不要把 key 写进 props，React 不会传入子组件。 */
function SeedMetric({
  label,
  value,
  icon: Icon,
  colorClass,
}: {
  label: string
  value: number
  icon: any
  colorClass: string
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
  )
}

function StatsCard({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: string | number
  icon: any
}) {
  return (
    <Card className="p-4 bg-bg-secondary border-border-default flex items-center gap-4">
      <div className="p-3 bg-bg-primary rounded-xl border border-border-default text-accent">
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-[10px] font-bold text-text-tertiary uppercase tracking-tighter">
          {label}
        </p>
        <p className="text-2xl font-mono font-bold">{value}</p>
      </div>
    </Card>
  )
}

function GraphLegendItem({
  swatch,
  title,
  description,
}: {
  swatch: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="rounded-xl border border-border-default bg-bg-primary px-3 py-3">
      <div className="flex items-center gap-3">
        <span className="inline-flex min-w-8 items-center justify-center">{swatch}</span>
        <div>
          <p className="text-xs font-bold text-text-primary">{title}</p>
          <p className="mt-1 text-[11px] leading-5 text-text-tertiary">{description}</p>
        </div>
      </div>
    </div>
  )
}
