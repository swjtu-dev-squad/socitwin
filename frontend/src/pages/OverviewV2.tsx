import { useState, useEffect, useMemo } from 'react'
import { useLocation } from 'react-router-dom'
import { toast } from 'sonner'
import { simulationApi } from '@/lib/api'
import { useSimulationStore } from '@/lib/store'
import {
  useSimulationStatusLightweight,
  useTopics,
  useMetricsHistory,
  useStepDrivenMetrics,
} from '@/hooks/useSimulationData'
import type { DatasetPlatform } from '@/components/SubscriptionPanel'
import type { PropagationMetrics, PolarizationMetrics, HerdEffectMetrics } from '@/lib/types'
import { SimulationHeader } from '@/components/overview/SimulationHeader'
import { ControlPanel } from '@/components/overview/ControlPanel'
import { MetricsGrid } from '@/components/overview/MetricsGrid'
import { SectionHeader } from '@/components/minimax-ui/SectionHeader'
import { SituationalAwarenessChart } from '@/components/SituationalAwarenessChart'

// 修复类型问题
const setSelectedPlatformWrapper = (setter: (platform: DatasetPlatform) => void) => {
  return (platform: string) => {
    setter(platform as DatasetPlatform)
  }
}

/**
 * OverviewV2 - 态势推演页面（MiniMax设计系统）
 * 深色主题，采用MiniMax设计语言
 */
function normalizeSimulationStatus(backendData: any): any {
  return {
    ...backendData,
    running: backendData.state === 'running',
    paused: backendData.state === 'paused',
    originalState: backendData.state,
    currentStep: backendData.current_step,
    currentRound: backendData.current_round,
    activeAgents: backendData.active_agents,
    totalPosts: backendData.total_posts,
    totalInteractions: backendData.total_interactions,
    agentCount: backendData.agent_count,
    totalSteps: backendData.total_steps,
    platform: backendData.platform,
    recsys: backendData.recsys,
    topics: backendData.topics,
    regions: backendData.regions,
  }
}

function getRequestErrorMessage(error: unknown): string {
  if (!error || typeof error !== 'object') {
    return '请求失败'
  }

  const maybeError = error as any
  return (
    maybeError?.response?.data?.detail ||
    maybeError?.response?.data?.message ||
    maybeError?.message ||
    '请求失败'
  )
}

export default function OverviewV2() {
  const { status, setStatus, isStepping, setIsStepping } = useSimulationStore()
  const location = useLocation()
  const initialFilters =
    (location.state as { selectedPlatform?: DatasetPlatform; selectedTopic?: string } | null) ??
    null

  // Use custom hooks for data fetching
  const {
    data: statusData,
    currentStep,
    refetch: refetchStatus,
  } = useSimulationStatusLightweight(2000)

  const [selectedPlatform, setSelectedPlatform] = useState<DatasetPlatform>(
    initialFilters?.selectedPlatform ?? 'twitter'
  )
  const { data: topics, isLoading: topicsLoading } = useTopics(selectedPlatform)
  const { data: chartHistory, isLoading: historyLoading } = useMetricsHistory(currentStep)
  const { latestMetrics } = useStepDrivenMetrics(currentStep || 0)

  // Fallback to chartHistory if latestMetrics doesn't have data
  const finalMetrics = useMemo(() => {
    let propagation: PropagationMetrics | null = latestMetrics?.propagation || null
    let polarization: PolarizationMetrics | null = latestMetrics?.polarization || null
    let herdEffect: HerdEffectMetrics | null = latestMetrics?.herdEffect || null

    // Fallback to chartHistory latest entry
    if (chartHistory && chartHistory.length > 0) {
      const latestEntry = chartHistory[chartHistory.length - 1]

      if (!propagation && latestEntry.propagation !== undefined) {
        propagation = {
          scale: latestEntry.propagation,
          depth: 0,
          max_breadth: 0,
          calculated_at: new Date().toISOString(),
        }
      }
      if (!polarization && latestEntry.polarization !== undefined) {
        polarization = {
          average_magnitude: latestEntry.polarization,
          average_direction: '0',
          total_agents_evaluated: 0,
          calculated_at: new Date().toISOString(),
        }
      }
      if (!herdEffect && latestEntry.herdEffect !== undefined) {
        herdEffect = {
          conformity_index: latestEntry.herdEffect,
          average_post_score: 0,
          disagree_score: 0,
          calculated_at: new Date().toISOString(),
        }
      }
    }

    return { propagation, polarization, herdEffect }
  }, [latestMetrics, chartHistory])

  // Use the latest status from hook if available, otherwise fall back to store
  const currentStatus = statusData || status

  // Local state for UI controls
  const [agentCount, setAgentCount] = useState([10])
  const [selectedTopic, setSelectedTopic] = useState<string>(initialFilters?.selectedTopic ?? '')
  const [isStarting, setIsStarting] = useState(false)

  const selectedTopicMeta = useMemo(
    () => topics.find(topic => topic.id === selectedTopic) || null,
    [topics, selectedTopic]
  )
  const availableUserCount = selectedTopicMeta?.user_count ?? 0

  const isSupportedSimulationPlatform =
    selectedPlatform === 'twitter' || selectedPlatform === 'reddit'

  // Update store status when hook data changes
  useEffect(() => {
    if (statusData) {
      setStatus(statusData)
    }
  }, [statusData, setStatus])

  // Keep topic selection aligned with the currently selected platform
  useEffect(() => {
    if (topics.length === 0) {
      setSelectedTopic('')
      return
    }

    const matchedTopic = topics.some(topic => topic.id === selectedTopic)
    if (!matchedTopic) {
      setSelectedTopic(topics[0].id)
    }
  }, [topics, selectedTopic])

  useEffect(() => {
    setAgentCount(prev => {
      if (availableUserCount <= 0) {
        return prev[0] === 0 ? prev : [0]
      }

      const nextValue = Math.min(Math.max(prev[0], 1), availableUserCount)
      return nextValue === prev[0] ? prev : [nextValue]
    })
  }, [availableUserCount])

  // Control handlers
  const handleStart = async () => {
    try {
      // 状态判断：优先使用 originalState，向后兼容 state 字段和布尔值
      const stateValue = currentStatus.originalState || currentStatus.state
      const isRunning =
        stateValue === 'running' || (!stateValue && currentStatus.running && !currentStatus.paused)

      if (isRunning) {
        await simulationApi.pause()
        const statusRes = await simulationApi.getStatus()
        setStatus(normalizeSimulationStatus(statusRes.data))
        await refetchStatus()
        toast.info('仿真已暂停')
        return
      }

      if (!selectedTopic) {
        toast.error('请先选择话题')
        return
      }

      if (!isSupportedSimulationPlatform) {
        toast.error('当前平台暂无可用仿真数据')
        return
      }

      if (availableUserCount <= 0) {
        toast.error('当前话题没有可用的原始用户')
        return
      }

      setIsStarting(true)
      toast.info('正在启动仿真...')

      const profilesResponse = await simulationApi.getTopicProfiles(selectedTopic, {
        platform: selectedPlatform,
        limit: agentCount[0],
      })
      const manualProfiles = profilesResponse.data.profiles ?? []

      if (manualProfiles.length === 0) {
        throw new Error('当前话题没有可用的原始用户')
      }

      const configResponse = await simulationApi.updateConfig({
        platform: selectedPlatform,
        agentCount: manualProfiles.length,
        maxSteps: 100,
        recsysType: selectedPlatform,
        agentSource: {
          sourceType: 'manual',
          manualConfig: manualProfiles.map(profile => profile.agent_config),
        },
      })

      if (configResponse.data?.success === false) {
        throw new Error(configResponse.data.message || '仿真配置失败')
      }

      const activationResponse = await simulationApi.activateTopic(selectedTopic, {
        platform: selectedPlatform,
      })

      if (activationResponse.data?.success === false) {
        throw new Error(activationResponse.data.message || '话题激活失败')
      }

      const stepResponse = await simulationApi.step('auto')
      const stepResult = stepResponse.data as any
      if (stepResult?.success === false) {
        throw new Error(stepResult.message || '仿真启动失败')
      }

      const statusRes = await simulationApi.getStatus()
      const normalizedStatus = normalizeSimulationStatus(statusRes.data)
      setStatus(normalizedStatus)
      await refetchStatus()

      toast.success(
        `仿真已启动: ${selectedTopicMeta?.name || selectedTopic} / 原始用户 ${manualProfiles.length} 人`
      )
    } catch (e) {
      console.error('启动失败:', e)
      toast.error(`启动失败: ${getRequestErrorMessage(e)}`)
    } finally {
      setIsStarting(false)
    }
  }

  const handlePause = async () => {
    try {
      await simulationApi.pause()
      const statusRes = await simulationApi.getStatus()
      setStatus(normalizeSimulationStatus(statusRes.data))
      await refetchStatus()
      toast.info('仿真已暂停')
    } catch (e) {
      console.error('暂停失败:', e)
      toast.error('暂停失败')
    }
  }

  const handleResume = async () => {
    try {
      const stepResponse = await simulationApi.step('auto')
      const stepResult = stepResponse.data as any
      if (stepResult?.success === false) {
        throw new Error(stepResult.message || '继续失败')
      }

      const statusRes = await simulationApi.getStatus()
      setStatus(normalizeSimulationStatus(statusRes.data))
      await refetchStatus()
      toast.success('仿真已继续')
    } catch (e) {
      console.error('继续失败:', e)
      toast.error(`继续失败: ${getRequestErrorMessage(e)}`)
    }
  }

  const handleReset = async () => {
    try {
      await simulationApi.reset()
      const statusRes = await simulationApi.getStatus()
      setStatus(normalizeSimulationStatus(statusRes.data))
      await refetchStatus()
      toast.success('仿真已重置')
    } catch (e) {
      console.error('重置失败:', e)
      toast.error('重置失败')
    }
  }

  const handleStep = async () => {
    setIsStepping(true)
    try {
      await simulationApi.step('auto')
      const res = await simulationApi.getStatus()
      setStatus(normalizeSimulationStatus(res.data))
      await refetchStatus()
      toast.success('步进完成')
    } catch (e) {
      console.error('步进失败:', e)
      toast.error('步进失败')
    } finally {
      setIsStepping(false)
    }
  }

  // 状态判断：优先使用 originalState，向后兼容 state 字段和布尔值
  const stateValue = currentStatus.originalState || currentStatus.state
  const isRunning =
    stateValue === 'running' || (!stateValue && currentStatus.running && !currentStatus.paused)
  const isPaused = stateValue === 'paused' || currentStatus.paused
  const isReady = stateValue === 'ready'

  const canStart =
    selectedTopic !== '' &&
    isSupportedSimulationPlatform &&
    availableUserCount > 0 &&
    !isRunning &&
    !isReady // ready状态也不能"开始仿真"

  // Prepare chart data (不再需要，SituationalAwarenessChart内部获取)
  // const chartData = useMemo(() => {
  //   if (!chartHistory || chartHistory.length === 0) {
  //     return []
  //   }
  //   return chartHistory.map(point => ({
  //     currentStep: point.step,
  //     polarization: point.polarization || 0,
  //     propagation: point.propagation || 0,
  //     herding: point.herdEffect || 0,
  //   }))
  // }, [chartHistory])

  return (
    <div className="min-h-screen py-10" style={{ background: '#181e25' }}>
      <div className="mx-auto" style={{ maxWidth: '1024px', padding: '0 24px' }}>
        <SimulationHeader status={currentStatus} />

        {/* 左右布局：控制面板 + 指标网格 */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
          {/* 左侧：仿真控制面板 - 占据3/4宽度 */}
          <div className="lg:col-span-3 flex flex-col">
            <div className="mb-4">
              <SectionHeader title="仿真控制" description="配置参数并控制仿真运行" />
            </div>
            <div className="flex-1">
              <ControlPanel
                selectedPlatform={selectedPlatform}
                onPlatformChange={setSelectedPlatformWrapper(setSelectedPlatform)}
                selectedTopic={selectedTopic}
                onTopicChange={setSelectedTopic}
                topics={topics}
                topicsLoading={topicsLoading}
                agentCount={agentCount}
                onAgentCountChange={setAgentCount}
                availableUserCount={availableUserCount}
                isRunning={isRunning}
                isPaused={isPaused}
                isReady={isReady}
                isStarting={isStarting}
                isStepping={isStepping}
                onStart={handleStart}
                onPause={handlePause}
                onResume={handleResume}
                onReset={handleReset}
                onStep={handleStep}
                canStart={canStart}
              />
            </div>
          </div>

          {/* 右侧：指标网格 - 占据1/4宽度，单列布局 */}
          <div className="lg:col-span-1 flex flex-col">
            <div className="mb-4">
              <SectionHeader title="实时指标" description="多维度指标监控" />
            </div>
            <div className="flex-1">
              <MetricsGrid
                propagation={finalMetrics.propagation}
                polarization={finalMetrics.polarization}
                herdEffect={finalMetrics.herdEffect}
                activeAgents={currentStatus.activeAgents || 0}
                isLoading={historyLoading}
              />
            </div>
          </div>
        </div>

        {/* 态势图表 */}
        <SectionHeader title="态势分析" description="多指标耦合分析与趋势预测" className="mb-6" />

        <div className="mb-8">
          <SituationalAwarenessChart currentStep={currentStep || 0} />
        </div>

        {/* 认知预警 */}
        {(isRunning || isPaused) && (
          <>
            <SectionHeader
              title="认知预警"
              description="基于多维度指标的智能风险评估"
              className="mb-6"
            />
            <div
              className="mb-8 p-6"
              style={{
                background: 'rgba(39, 39, 54, 0.2)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                borderRadius: '8px',
              }}
            >
              <p
                className="text-sm"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#71717a',
                }}
              >
                仿真运行中，实时监控认知风险指标...
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
