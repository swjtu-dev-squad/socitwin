import { Database, Sliders } from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import type { DatasetPlatform } from '@/components/SubscriptionPanel'

/**
 * ControlPanel - 科技风控制面板
 * 细线框 + 毛玻璃 + 刻度尺风格
 */
interface ControlPanelProps {
  selectedPlatform: DatasetPlatform
  onPlatformChange: (platform: string) => void
  selectedTopic: string
  onTopicChange: (topic: string) => void
  topics: any[]
  topicsLoading: boolean
  agentCount: number[]
  onAgentCountChange: (count: number[]) => void
  availableUserCount: number
  isRunning: boolean
  isPaused: boolean
  isReady: boolean
  isStarting: boolean
  isStepping: boolean
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onReset: () => void
  onStep: () => void
  canStart: boolean
}

const platformLabelMap: Record<DatasetPlatform, string> = {
  twitter: 'X / Twitter',
  reddit: 'Reddit',
  tiktok: 'TikTok',
  instagram: 'Instagram',
  facebook: 'Facebook',
}

export function ControlPanel({
  selectedPlatform,
  onPlatformChange,
  selectedTopic,
  onTopicChange,
  topics,
  topicsLoading,
  agentCount,
  onAgentCountChange,
  availableUserCount,
  isRunning,
  isPaused,
  isReady,
  isStarting,
  isStepping,
  onStart,
  onPause,
  onResume,
  onReset,
  onStep,
  canStart,
}: ControlPanelProps) {
  return (
    <div
      className="h-full p-6 transition-all duration-300"
      style={{
        background: 'rgba(39, 39, 54, 0.3)',
        backdropFilter: 'blur(20px)',
        borderRadius: '16px',
        border: '1px solid rgba(59, 130, 246, 0.3)',
        boxShadow: '0 0 40px rgba(59, 130, 246, 0.1)',
      }}
    >
      <div className="flex-1 space-y-8">
        {/* 数据源配置 */}
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <div
              className="flex items-center justify-center w-8 h-8"
              style={{
                background: 'rgba(0, 242, 255, 0.1)',
                borderRadius: '4px',
                border: '1px solid rgba(0, 242, 255, 0.3)',
              }}
            >
              <Database className="w-4 h-4" style={{ color: '#00f2ff' }} />
            </div>
            <div>
              <h3
                className="text-sm font-semibold tracking-wider"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#00f2ff',
                  letterSpacing: '0.1em',
                }}
              >
                数据源
              </h3>
              <p
                className="text-xs mt-0.5"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#71717a',
                }}
              >
                数据源配置
              </p>
            </div>
          </div>

          {/* 平台和话题选择 - 细线框风格 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label
                className="text-xs font-medium block"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#00f2ff',
                  letterSpacing: '0.05em',
                }}
              >
                平台
              </label>
              <Select value={selectedPlatform} onValueChange={onPlatformChange}>
                <SelectTrigger
                  className="w-full"
                  style={{
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(0, 242, 255, 0.3)',
                    borderRadius: '2px',
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: '13px',
                    color: '#fafafa',
                    letterSpacing: '0.05em',
                  }}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent
                  className="tech-select-dropdown"
                  style={{
                    background: 'rgba(24, 30, 37, 0.98)',
                    border: '1px solid rgba(0, 242, 255, 0.3)',
                    borderRadius: '2px',
                    fontFamily: '"JetBrains Mono", monospace',
                  }}
                >
                  {Object.entries(platformLabelMap).map(([key, label]) => (
                    <SelectItem
                      key={key}
                      value={key}
                      className="tech-select-item"
                      style={{
                        color: '#fafafa',
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: '13px',
                      }}
                    >
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label
                className="text-xs font-medium block"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#00f2ff',
                  letterSpacing: '0.05em',
                }}
              >
                话题
              </label>
              <Select value={selectedTopic} onValueChange={onTopicChange}>
                <SelectTrigger
                  className="w-full"
                  style={{
                    background: 'rgba(0, 0, 0, 0.3)',
                    border: '1px solid rgba(0, 242, 255, 0.3)',
                    borderRadius: '2px',
                    fontFamily: '"JetBrains Mono", monospace',
                    fontSize: '13px',
                    color: '#fafafa',
                    letterSpacing: '0.05em',
                  }}
                >
                  <SelectValue
                    placeholder={
                      topicsLoading ? '加载中...' : topics.length === 0 ? '无数据' : '选择话题'
                    }
                  />
                </SelectTrigger>
                <SelectContent
                  className="tech-select-dropdown"
                  style={{
                    background: 'rgba(24, 30, 37, 0.98)',
                    border: '1px solid rgba(0, 242, 255, 0.3)',
                    borderRadius: '2px',
                    fontFamily: '"JetBrains Mono", monospace',
                  }}
                >
                  {topics.map(topic => (
                    <SelectItem
                      key={topic.id}
                      value={topic.id}
                      className="tech-select-item"
                      style={{
                        color: '#fafafa',
                        fontFamily: '"JetBrains Mono", monospace',
                        fontSize: '13px',
                      }}
                    >
                      {topic.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 智能体数量控制 - 精密仪器刻度尺 */}
          <div
            className="space-y-4 p-5"
            style={{
              background: 'rgba(0, 0, 0, 0.2)',
              borderRadius: '8px',
              position: 'relative',
            }}
          >
            <div className="flex items-center justify-between">
              <label
                className="text-xs font-semibold"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#00f2ff',
                  letterSpacing: '0.05em',
                }}
              >
                智能体数量
              </label>
              <div
                className="text-xl font-bold"
                style={{
                  fontFamily: '"DIN Alternate", "JetBrains Mono", monospace',
                  color: '#00f2ff',
                  textShadow: '0 0 10px rgba(0, 242, 255, 0.5)',
                }}
              >
                {String(agentCount[0]).padStart(3, '0')}
              </div>
            </div>

            <div className="relative py-4">
              <Slider
                value={agentCount}
                onValueChange={onAgentCountChange}
                max={availableUserCount}
                min={1}
                step={1}
                className="w-full"
              />
              {/* 刻度线装饰 */}
              <div
                className="absolute top-1/2 left-0 right-0 h-px"
                style={{
                  background:
                    'linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.15) 50%, transparent)',
                  transform: 'translateY(-50%)',
                  pointerEvents: 'none',
                }}
              />
            </div>

            <div
              className="flex items-center justify-between text-xs"
              style={{ fontFamily: '"JetBrains Mono", monospace', color: '#52525b' }}
            >
              <span>001</span>
              <span>{String(availableUserCount).padStart(3, '0')}</span>
            </div>
          </div>
        </div>

        {/* 仿真控制 */}
        <div className="space-y-4 pt-6" style={{ borderTop: '1px solid rgba(59, 130, 246, 0.2)' }}>
          <div className="flex items-center gap-3">
            <div
              className="flex items-center justify-center w-8 h-8"
              style={{
                background: 'rgba(234, 94, 193, 0.1)',
                borderRadius: '4px',
                border: '1px solid rgba(234, 94, 193, 0.3)',
              }}
            >
              <Sliders className="w-4 h-4" style={{ color: '#ea5ec1' }} />
            </div>
            <div>
              <h3
                className="text-sm font-semibold tracking-wider"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#ea5ec1',
                  letterSpacing: '0.1em',
                }}
              >
                控制
              </h3>
              <p
                className="text-xs mt-0.5"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#71717a',
                }}
              >
                仿真控制
              </p>
            </div>
          </div>

          {/* 控制按钮 */}
          <div className="flex items-center gap-3 flex-wrap">
            {!isRunning && !isPaused && !isReady && (
              <button
                onClick={onStart}
                disabled={!canStart || isStarting}
                className="px-6 py-2 text-sm font-medium transition-all duration-200"
                style={{
                  background: 'rgba(0, 242, 255, 0.1)',
                  border: '1px solid #00f2ff',
                  borderRadius: '2px',
                  color: '#00f2ff',
                  fontFamily: '"JetBrains Mono", monospace',
                  letterSpacing: '0.05em',
                  opacity: !canStart || isStarting ? 0.5 : 1,
                  cursor: !canStart || isStarting ? 'not-allowed' : 'pointer',
                  textShadow: '0 0 10px rgba(0, 242, 255, 0.3)',
                }}
              >
                {isStarting ? '初始化中...' : '▶ 开始'}
              </button>
            )}

            {isReady && !isRunning && !isPaused && (
              <>
                <button
                  onClick={onStep}
                  disabled={isStepping}
                  className="px-5 py-2 text-sm font-medium transition-all duration-200"
                  style={{
                    background: 'rgba(0, 242, 255, 0.1)',
                    border: '1px solid #00f2ff',
                    borderRadius: '2px',
                    color: '#00f2ff',
                    fontFamily: '"JetBrains Mono", monospace',
                    letterSpacing: '0.05em',
                    opacity: isStepping ? 0.5 : 1,
                    textShadow: '0 0 10px rgba(0, 242, 255, 0.3)',
                  }}
                >
                  ▶ 单步执行
                </button>
                <button
                  onClick={onReset}
                  className="px-5 py-2 text-sm font-medium transition-all duration-200"
                  style={{
                    background: 'transparent',
                    border: '1px solid #52525b',
                    borderRadius: '2px',
                    color: '#71717a',
                    fontFamily: '"JetBrains Mono", monospace',
                    letterSpacing: '0.05em',
                  }}
                >
                  ↺ 重置
                </button>
              </>
            )}

            {isRunning && (
              <button
                onClick={onPause}
                className="px-5 py-2 text-sm font-medium transition-all duration-200"
                style={{
                  background: 'rgba(234, 94, 193, 0.1)',
                  border: '1px solid #ea5ec1',
                  borderRadius: '2px',
                  color: '#ea5ec1',
                  fontFamily: '"JetBrains Mono", monospace',
                  letterSpacing: '0.05em',
                  textShadow: '0 0 10px rgba(234, 94, 193, 0.3)',
                }}
              >
                ⏸ 暂停
              </button>
            )}

            {isPaused && (
              <>
                <button
                  onClick={onResume}
                  className="px-5 py-2 text-sm font-medium transition-all duration-200"
                  style={{
                    background: 'rgba(0, 242, 255, 0.1)',
                    border: '1px solid #00f2ff',
                    borderRadius: '2px',
                    color: '#00f2ff',
                    fontFamily: '"JetBrains Mono", monospace',
                    letterSpacing: '0.05em',
                    textShadow: '0 0 10px rgba(0, 242, 255, 0.3)',
                  }}
                >
                  ▶ 继续
                </button>
                <button
                  onClick={onStep}
                  disabled={isStepping}
                  className="px-5 py-2 text-sm font-medium transition-all duration-200"
                  style={{
                    background: 'rgba(0, 242, 255, 0.1)',
                    border: '1px solid #00f2ff',
                    borderRadius: '2px',
                    color: '#00f2ff',
                    fontFamily: '"JetBrains Mono", monospace',
                    letterSpacing: '0.05em',
                    opacity: isStepping ? 0.5 : 1,
                    textShadow: '0 0 10px rgba(0, 242, 255, 0.3)',
                  }}
                >
                  ▶ 单步执行
                </button>
              </>
            )}

            {(isRunning || isPaused) && (
              <button
                onClick={onReset}
                className="px-5 py-2 text-sm font-medium transition-all duration-200"
                style={{
                  background: 'transparent',
                  border: '1px solid #52525b',
                  borderRadius: '2px',
                  color: '#71717a',
                  fontFamily: '"JetBrains Mono", monospace',
                  letterSpacing: '0.05em',
                }}
              >
                ↺ 重置
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
