import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

/**
 * MetricCard - MiniMax风格指标卡片（深色主题）
 */
interface MetricCardProps {
  title: string
  value: string | number
  unit?: string
  description?: string
  icon?: LucideIcon
  trend?: {
    value: number
    isPositive: boolean
  }
  color?: 'rose' | 'emerald' | 'amber' | 'blue'
  className?: string
}

const colorMap = {
  rose: '#f43f5e',
  emerald: '#10b981',
  amber: '#f59e0b',
  blue: '#3b82f6',
}

const colorBgMap = {
  rose: 'rgba(244, 63, 94, 0.15)',
  emerald: 'rgba(16, 185, 129, 0.15)',
  amber: 'rgba(245, 158, 11, 0.15)',
  blue: 'rgba(59, 130, 246, 0.15)',
}

export function MetricCard({
  title,
  value,
  unit,
  description,
  icon: Icon,
  trend,
  color = 'blue',
  className,
}: MetricCardProps) {
  const colorValue = colorMap[color]
  const colorBg = colorBgMap[color]

  return (
    <div
      className={cn('border p-4 transition-all duration-200', className)}
      style={{
        background: '#27272a',
        borderColor: '#3f3f46',
        borderRadius: '16px',
        boxShadow: 'rgba(0, 0, 0, 0.3) 0px 2px 8px',
      }}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p
            className="text-sm font-medium mb-1"
            style={{
              fontFamily: 'DM Sans, sans-serif',
              color: '#a1a1aa',
            }}
          >
            {title}
          </p>
          <div className="flex items-baseline gap-1">
            <span
              className="text-2xl font-semibold"
              style={{
                fontFamily: 'Roboto, sans-serif',
                color: '#fafafa',
              }}
            >
              {typeof value === 'number' ? value.toLocaleString() : value}
            </span>
            {unit && (
              <span
                className="text-xs"
                style={{
                  fontFamily: 'DM Sans, sans-serif',
                  color: '#71717a',
                }}
              >
                {unit}
              </span>
            )}
          </div>
          {description && (
            <p
              className="text-xs mt-1"
              style={{
                fontFamily: 'DM Sans, sans-serif',
                color: '#71717a',
              }}
            >
              {description}
            </p>
          )}
          {trend && (
            <div className="flex items-center gap-1 mt-2">
              <span
                className="text-xs font-medium"
                style={{
                  color: trend.isPositive ? '#10b981' : '#f43f5e',
                }}
              >
                {trend.isPositive ? '+' : '-'}
                {Math.abs(trend.value)}%
              </span>
              <span className="text-xs" style={{ color: '#71717a' }}>
                较上步
              </span>
            </div>
          )}
        </div>
        {Icon && (
          <div
            className="p-2.5 rounded-lg"
            style={{
              backgroundColor: colorBg,
            }}
          >
            <Icon className="w-5 h-5" style={{ color: colorValue }} />
          </div>
        )}
      </div>
    </div>
  )
}
