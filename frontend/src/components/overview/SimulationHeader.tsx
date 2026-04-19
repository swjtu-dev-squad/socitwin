import { Activity } from 'lucide-react'
import { StatusIndicator } from '@/components/minimax-ui/StatusIndicator'
import type { SimulationStatus } from '@/lib/types'

/**
 * SimulationHeader - 科技风页面头部
 * 等宽字体 + 霓虹光效 + 装饰线
 */
interface SimulationHeaderProps {
  status: SimulationStatus | null
}

export function SimulationHeader({ status }: SimulationHeaderProps) {
  const getStatusValue = (): 'running' | 'paused' | 'ready' | 'error' | 'idle' => {
    if (!status) return 'idle'

    if (status.originalState === 'running') return 'running'
    if (status.originalState === 'paused') return 'paused'
    if (status.originalState === 'ready') return 'ready'
    if (status.originalState === 'error') return 'error'

    if (status.running) return 'running'
    if (status.paused) return 'paused'
    if (status.initializationComplete) return 'ready'
    if (status.initializationPhase) return 'running'

    return 'idle'
  }

  return (
    <div className="mb-12">
      {/* 主标题区域 */}
      <div
        className="flex items-center justify-between mb-8 pb-6"
        style={{
          borderBottom: '1px solid rgba(0, 242, 255, 0.2)',
          position: 'relative',
        }}
      >
        {/* 装饰性扫描线 */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '2px',
            background: 'linear-gradient(90deg, transparent 0%, #00f2ff 50%, transparent 100%)',
            animation: 'scan 3s linear infinite',
          }}
        />

        <div>
          <h1
            className="font-light tracking-wider"
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '56px',
              color: '#fafafa',
              lineHeight: '1',
              letterSpacing: '0.15em',
              textShadow: '0 0 40px rgba(0, 242, 255, 0.5)',
            }}
          >
            态势感知
          </h1>
          <p
            className="mt-2"
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '13px',
              color: '#71717a',
              letterSpacing: '0.05em',
            }}
          >
            社交网络仿真与群体极化分析
          </p>
        </div>

        <div className="flex items-center gap-4">
          <StatusIndicator status={getStatusValue()} />
        </div>
      </div>

      {/* 状态统计 - 等宽字体 */}
      {status && (
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3">
            <Activity className="w-4 h-4" style={{ color: '#00f2ff', opacity: 0.6 }} />
            <span
              className="text-xs mr-2"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#71717a',
                letterSpacing: '0.05em',
              }}
            >
              活跃智能体
            </span>
            <span
              className="text-lg font-semibold"
              style={{
                fontFamily: '"DIN Alternate", "JetBrains Mono", monospace',
                color: '#00f2ff',
                textShadow: '0 0 20px rgba(0, 242, 255, 0.4)',
              }}
            >
              {status.activeAgents?.toLocaleString() || 0}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span
              className="text-xs"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#71717a',
                letterSpacing: '0.05em',
              }}
            >
              当前步数
            </span>
            <span
              className="text-lg font-semibold"
              style={{
                fontFamily: '"DIN Alternate", "JetBrains Mono", monospace',
                color: '#00f2ff',
                textShadow: '0 0 20px rgba(0, 242, 255, 0.4)',
              }}
            >
              {status.currentStep?.toLocaleString() || 0}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span
              className="text-xs"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#71717a',
                letterSpacing: '0.05em',
              }}
            >
              总帖子数
            </span>
            <span
              className="text-lg font-semibold"
              style={{
                fontFamily: '"DIN Alternate", "JetBrains Mono", monospace',
                color: '#00f2ff',
                textShadow: '0 0 20px rgba(0, 242, 255, 0.4)',
              }}
            >
              {status.totalPosts?.toLocaleString() || 0}
            </span>
          </div>

          {status.platform && (
            <div className="flex items-center gap-3">
              <span
                className="text-xs"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  color: '#71717a',
                  letterSpacing: '0.05em',
                }}
              >
                平台
              </span>
              <span
                className="text-lg font-semibold"
                style={{
                  fontFamily: '"DIN Alternate", "JetBrains Mono", monospace',
                  color: '#00f2ff',
                  textShadow: '0 0 20px rgba(0, 242, 255, 0.4)',
                }}
              >
                {status.platform.toUpperCase()}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
