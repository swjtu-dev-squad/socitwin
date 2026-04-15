import { useState } from 'react'
import {
  FlaskConical,
  Archive,
  Play,
  Plus,
  Search,
  Filter,
  ChevronRight,
  Settings2,
} from 'lucide-react'
import { Card, Button, Badge, Input, ScrollArea } from '@/components/ui'
import { cn } from '@/lib/utils'
import type { PlatformStrategy, InferenceTask } from '@/lib/labTypes'
import { LabParamSettings } from '@/components/LabParamSettings'
import { InferenceMonitorCard } from '@/components/InferenceMonitorCard'

type Tab = 'runner' | 'params' | 'archive'

const INITIAL_PLATFORMS: PlatformStrategy[] = [
  {
    id: 'tiktok',
    name: 'TikTok',
    params: {
      interestWeight: 0.8,
      socialWeight: 0.2,
      recencyWeight: 0.9,
      qualityWeight: 0.4,
      explorationRate: 0.7,
    },
  },
  {
    id: 'xiaohongshu',
    name: '小红书',
    params: {
      interestWeight: 0.6,
      socialWeight: 0.7,
      recencyWeight: 0.5,
      qualityWeight: 0.8,
      explorationRate: 0.4,
    },
  },
  {
    id: 'pinterest',
    name: 'Pinterest',
    params: {
      interestWeight: 0.9,
      socialWeight: 0.3,
      recencyWeight: 0.2,
      qualityWeight: 0.7,
      explorationRate: 0.6,
    },
  },
  {
    id: 'reddit',
    name: 'Reddit',
    params: {
      interestWeight: 0.5,
      socialWeight: 0.8,
      recencyWeight: 0.6,
      qualityWeight: 0.9,
      explorationRate: 0.3,
    },
  },
  {
    id: 'twitter',
    name: 'X/Twitter',
    params: {
      interestWeight: 0.4,
      socialWeight: 0.6,
      recencyWeight: 0.95,
      qualityWeight: 0.3,
      explorationRate: 0.8,
    },
  },
]

const MOCK_TASKS: InferenceTask[] = [
  {
    id: 'task-1',
    name: 'TikTok 算法极化推演',
    status: 'running',
    progress: 45,
    datasetId: 'ds-001',
    baselineId: 'baseline-tiktok-2023',
    platformConfigs: [],
    metrics: {
      currentPolarization: 0.65,
      baselinePolarization: 0.62,
      fitScore: 88.5,
      biasValue: +4.8,
    },
    stepsTrace: Array.from({ length: 20 }, (_, i) => ({
      step: i,
      simValue: 0.3 + i * 0.02 + Math.random() * 0.05,
      baseValue: 0.3 + i * 0.018 + Math.random() * 0.02,
    })),
  },
  {
    id: 'task-2',
    name: '小红书 社区氛围模拟',
    status: 'running',
    progress: 72,
    datasetId: 'ds-002',
    baselineId: 'baseline-xhs-2023',
    platformConfigs: [],
    metrics: {
      currentPolarization: 0.35,
      baselinePolarization: 0.38,
      fitScore: 92.1,
      biasValue: -7.8,
    },
    stepsTrace: Array.from({ length: 30 }, (_, i) => ({
      step: i,
      simValue: 0.2 + i * 0.005 + Math.random() * 0.03,
      baseValue: 0.2 + i * 0.006 + Math.random() * 0.02,
    })),
  },
]

export default function Experiments() {
  const [activeTab, setActiveTab] = useState<Tab>('runner')
  const [platforms, setPlatforms] = useState<PlatformStrategy[]>(INITIAL_PLATFORMS)

  const tabs = [
    { id: 'runner', label: '运行实验', icon: Play },
    { id: 'params', label: '参数微调', icon: Settings2 },
    { id: 'archive', label: '历史归档', icon: Archive },
  ]

  const handleParamUpdate = (
    platformId: string,
    paramKey: keyof PlatformStrategy['params'],
    value: number
  ) => {
    setPlatforms(prev =>
      prev.map(p =>
        p.id === platformId ? { ...p, params: { ...p.params, [paramKey]: value } } : p
      )
    )
  }

  return (
    <div className="px-6 lg:px-12 py-10 space-y-8">
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <FlaskConical className="w-10 h-10 text-accent" />
            社交平台实验室
          </h1>
          <p className="text-text-tertiary mt-1">设计、执行并对比不同推荐策略对社会动力学的影响</p>
        </div>
        <div className="flex bg-bg-secondary p-1 rounded-2xl border border-border-default">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={cn(
                'flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all',
                activeTab === tab.id
                  ? 'bg-accent text-bg-primary shadow-lg shadow-accent/10'
                  : 'text-text-tertiary hover:text-text-secondary'
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-8">
        {activeTab === 'runner' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <Card className="lg:col-span-4 bg-bg-secondary border-border-default p-8 space-y-8 h-fit">
              <h2 className="text-xl font-bold flex items-center gap-2">
                <Plus className="w-5 h-5 text-accent" />
                新建实验任务
              </h2>

              <div className="space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    实验名称
                  </label>
                  <Input
                    placeholder="例如: TikTok vs XHS 极化对比"
                    className="bg-bg-primary border-border-default rounded-xl"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    选择数据集
                  </label>
                  <select className="w-full h-11 bg-bg-primary border border-border-default rounded-xl px-4 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/20">
                    <option>Reddit Demo Dataset</option>
                    <option>Twitter Global Sample</option>
                    <option>Custom Dataset #1</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    参照基准 (Baseline)
                  </label>
                  <select className="w-full h-11 bg-bg-primary border border-border-default rounded-xl px-4 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/20">
                    <option>baseline-tiktok-2023</option>
                    <option>baseline-xhs-2023</option>
                    <option>baseline-twitter-2024</option>
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-widest text-text-tertiary">
                    对比策略
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    {platforms.map(platform => (
                      <label
                        key={platform.id}
                        className="flex items-center gap-3 p-3 rounded-xl bg-bg-primary border border-border-default cursor-pointer hover:border-accent/30 transition-colors"
                      >
                        <input
                          type="checkbox"
                          className="w-4 h-4 accent-accent"
                          defaultChecked={['tiktok', 'xiaohongshu'].includes(platform.id)}
                        />
                        <span className="text-sm font-medium">{platform.name}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <Button className="w-full h-14 text-lg font-bold rounded-2xl shadow-xl shadow-accent/10">
                  <Play className="w-5 h-5 mr-2 fill-current" />
                  启动并行实验
                </Button>
              </div>
            </Card>

            <Card className="lg:col-span-8 bg-bg-secondary border-border-default flex flex-col overflow-hidden min-h-[500px]">
              <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
                <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary">
                  活跃任务队列与拟合监控
                </h2>
                <Badge variant="outline">{MOCK_TASKS.length} Running</Badge>
              </div>
              <div className="flex-1 p-6 space-y-6 overflow-y-auto custom-scrollbar">
                {MOCK_TASKS.map(task => (
                  <InferenceMonitorCard key={task.id} task={task} />
                ))}
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'params' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {platforms.map(platform => (
              <LabParamSettings
                key={platform.id}
                platform={platform}
                onUpdate={handleParamUpdate}
              />
            ))}
          </div>
        )}

        {activeTab === 'archive' && (
          <Card className="bg-bg-secondary border-border-default overflow-hidden">
            <div className="p-6 border-b border-border-default bg-bg-secondary/50 flex flex-wrap gap-4 items-center">
              <div className="relative flex-1 min-w-[300px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
                <Input
                  placeholder="搜索实验记录..."
                  className="pl-10 h-11 rounded-xl bg-bg-primary border-border-default"
                />
              </div>
              <Button variant="outline" className="h-11 rounded-xl gap-2">
                <Filter className="w-4 h-4" />
                筛选
              </Button>
            </div>
            <ScrollArea className="h-[600px]">
              <div className="divide-y divide-border-default/50">
                {[1, 2, 3, 4, 5].map(i => (
                  <div
                    key={i}
                    className="p-6 hover:bg-bg-tertiary/30 transition-all flex items-center justify-between group cursor-pointer"
                  >
                    <div className="flex items-center gap-6">
                      <div className="w-12 h-12 rounded-xl bg-bg-primary border border-border-default flex items-center justify-center text-text-tertiary group-hover:text-accent group-hover:border-accent/30 transition-all">
                        <Archive className="w-6 h-6" />
                      </div>
                      <div>
                        <h4 className="font-bold text-text-primary">策略敏感度分析 v{i}.0</h4>
                        <div className="flex items-center gap-3 mt-1 text-xs text-text-tertiary">
                          <span>2026-03-{20 - i}</span>
                          <span>·</span>
                          <span>100 Agents</span>
                          <span>·</span>
                          <span className="text-accent font-bold">Success</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-8">
                      <div className="text-right hidden md:block">
                        <p className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">
                          Fit Score
                        </p>
                        <p className="text-lg font-mono font-bold text-emerald-500">
                          {80 + i * 2}%
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-text-muted group-hover:text-text-primary transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </Card>
        )}
      </div>
    </div>
  )
}
