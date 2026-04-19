import { cn } from '@/lib/utils'

/**
 * StatusIndicator - 科技风状态指示器
 * 等宽字体 + 扫描动效
 */
interface StatusIndicatorProps {
  status: 'running' | 'paused' | 'ready' | 'error' | 'idle'
  label?: string
  className?: string
}

export function StatusIndicator({ status, label, className }: StatusIndicatorProps) {
  const statusConfig = {
    running: {
      color: '#10b981',
      bgColor: 'rgba(16, 185, 129, 0.1)',
      borderColor: 'rgba(16, 185, 129, 0.4)',
      textColor: '#10b981',
      defaultLabel: '运行中',
      animated: true,
    },
    paused: {
      color: '#f59e0b',
      bgColor: 'rgba(245, 158, 11, 0.1)',
      borderColor: 'rgba(245, 158, 11, 0.4)',
      textColor: '#f59e0b',
      defaultLabel: '已暂停',
      animated: false,
    },
    ready: {
      color: '#00f2ff',
      bgColor: 'rgba(0, 242, 255, 0.1)',
      borderColor: 'rgba(0, 242, 255, 0.4)',
      textColor: '#00f2ff',
      defaultLabel: '就绪',
      animated: false,
    },
    error: {
      color: '#f43f5e',
      bgColor: 'rgba(244, 63, 94, 0.1)',
      borderColor: 'rgba(244, 63, 94, 0.4)',
      textColor: '#f43f5e',
      defaultLabel: '错误',
      animated: false,
    },
    idle: {
      color: '#71717a',
      bgColor: 'rgba(113, 113, 122, 0.1)',
      borderColor: 'rgba(113, 113, 122, 0.4)',
      textColor: '#71717a',
      defaultLabel: '空闲',
      animated: false,
    },
  }

  const config = statusConfig[status]
  const displayLabel = label || config.defaultLabel

  return (
    <div
      className={cn('inline-flex items-center gap-2 px-4 py-2', className)}
      style={{
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: '12px',
        fontWeight: 500,
        letterSpacing: '0.05em',
        background: config.bgColor,
        border: `1px solid ${config.borderColor}`,
        borderRadius: '2px',
        color: config.textColor,
        textShadow: `0 0 10px ${config.color}30`,
      }}
    >
      <span
        className={cn('w-1.5 h-1.5 rounded-full', config.animated && 'animate-pulse')}
        style={{
          backgroundColor: config.color,
          boxShadow: `0 0 8px ${config.color}`,
        }}
      />
      <span>{displayLabel}</span>
    </div>
  )
}
