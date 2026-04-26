import React from 'react'
import { Share2, TrendingUp, Users, Activity } from 'lucide-react'
import type { PropagationMetrics, PolarizationMetrics, HerdEffectMetrics } from '@/lib/types'

/**
 * MetricsGrid - 科技风指标网格
 * 细线框 + 等宽数字 + 微型趋势图
 */
interface MetricsGridProps {
  propagation: PropagationMetrics | null
  polarization: PolarizationMetrics | null
  herdEffect: HerdEffectMetrics | null
  activeAgents: number
  isLoading: boolean
}

export function MetricsGrid({
  propagation,
  polarization,
  herdEffect,
  activeAgents,
  isLoading,
}: MetricsGridProps) {
  const propagationValue = React.useMemo(() => {
    if (propagation?.scale === null || propagation?.scale === undefined) return null
    return propagation.scale
  }, [propagation])

  const polarizationValue = React.useMemo(() => {
    if (polarization?.average_magnitude === null || polarization?.average_magnitude === undefined)
      return null
    return polarization.average_magnitude * 100
  }, [polarization])

  const herdEffectValue = React.useMemo(() => {
    if (herdEffect?.conformity_index === null || herdEffect?.conformity_index === undefined)
      return null
    return herdEffect.conformity_index * 100
  }, [herdEffect])

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map(i => (
          <div
            key={i}
            className="animate-pulse relative"
            style={{
              background: 'rgba(39, 39, 54, 0.2)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
              borderRadius: '8px',
              padding: '16px',
              minHeight: '160px', // 固定高度，与实际内容一致
            }}
          >
            {/* 装饰性角标 */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '6px',
                height: '6px',
                borderTop: '1px solid rgba(59, 130, 246, 0.3)',
                borderLeft: '1px solid rgba(59, 130, 246, 0.3)',
              }}
            />

            {/* 标题骨架 */}
            <div className="flex items-center gap-2 mb-2">
              <div
                className="h-3 rounded"
                style={{ background: 'rgba(59, 130, 246, 0.1)', width: '80px' }}
              ></div>
              <div
                className="h-3 w-3 rounded"
                style={{ background: 'rgba(59, 130, 246, 0.1)' }}
              ></div>
            </div>

            {/* 标签骨架 */}
            <div
              className="h-3 rounded mb-3"
              style={{ background: 'rgba(59, 130, 246, 0.1)', width: '100px' }}
            ></div>

            {/* 数值骨架 */}
            <div
              className="h-8 rounded mb-2"
              style={{ background: 'rgba(59, 130, 246, 0.1)', width: '120px' }}
            ></div>

            {/* 趋势图骨架 */}
            <div
              className="h-6 rounded"
              style={{ background: 'rgba(59, 130, 246, 0.1)', width: '80px' }}
            ></div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* 信息传播 */}
      <MetricCard
        title="信息传播"
        label="传播覆盖范围"
        value={propagationValue}
        unit="人"
        icon={Share2}
        color="blue"
        trend={[0.2, 0.15, 0.3, 0.25, 0.2]}
      />

      {/* 群体极化 */}
      <MetricCard
        title="群体极化"
        label="意见分化程度"
        value={polarizationValue}
        unit="%"
        icon={TrendingUp}
        color={
          polarizationValue !== null && polarizationValue > 60
            ? 'rose'
            : polarizationValue !== null && polarizationValue > 30
              ? 'amber'
              : 'emerald'
        }
        trend={[0.1, 0.15, 0.2, 0.18, 0.22]}
      />

      {/* 从众效应 */}
      <MetricCard
        title="从众效应"
        label="群体一致性"
        value={herdEffectValue}
        unit="%"
        icon={Users}
        color={
          herdEffectValue !== null && herdEffectValue > 50
            ? 'rose'
            : herdEffectValue !== null && herdEffectValue > 30
              ? 'amber'
              : 'emerald'
        }
        trend={[0.3, 0.25, 0.2, 0.35, 0.3]}
      />

      {/* 活跃智能体 */}
      <MetricCard
        title="活跃智能体"
        label="参与互动数量"
        value={activeAgents}
        unit="人"
        icon={Activity}
        color="blue"
        trend={[10, 11, 10, 12, activeAgents]}
      />
    </div>
  )
}

/**
 * MetricCard - 科技风指标卡片
 * 细线框 + 等宽数字 + 微型趋势图
 */
interface MetricCardProps {
  title: string
  label: string
  value: number | null
  unit?: string
  description?: string
  icon?: any
  color?: 'rose' | 'emerald' | 'amber' | 'blue'
  trend?: number[]
  className?: string
}

const colorMap = {
  rose: '#f43f5e',
  emerald: '#10b981',
  amber: '#f59e0b',
  blue: '#00f2ff',
}

function MetricCard({
  title,
  label,
  value,
  unit,
  description,
  icon: Icon,
  color = 'blue',
  trend,
}: MetricCardProps) {
  const colorValue = colorMap[color]

  // 格式化数值显示
  const formatValue = (val: number | null, unit?: string): string => {
    if (val === null) return '--'
    if (unit === '%') {
      return val.toFixed(1) + unit
    } else if (unit === '人') {
      return Math.round(val).toLocaleString() + unit
    } else {
      return val.toFixed(1)
    }
  }

  // 生成微型趋势图SVG
  const sparkline = trend ? (
    <svg
      width="80"
      height="24"
      viewBox={`0 0 80 ${trend.length * 16}`}
      style={{ overflow: 'visible' }}
    >
      <polyline
        points={trend.map((v, i) => `${i * 16},${24 - v * 24}`).join(' ')}
        fill="none"
        stroke={colorValue}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          filter: `drop-shadow(0 0 4px ${colorValue}40)`,
        }}
      />
    </svg>
  ) : null

  return (
    <div
      className="relative p-4 transition-all duration-200 hover:border-opacity-100"
      style={{
        background: 'rgba(39, 39, 54, 0.2)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(59, 130, 246, 0.2)',
        borderRadius: '8px',
        minHeight: '160px', // 确保高度一致，避免加载时抖动
      }}
    >
      {/* 装饰性角标 */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '6px',
          height: '6px',
          borderTop: '1px solid rgba(59, 130, 246, 0.3)',
          borderLeft: '1px solid rgba(59, 130, 246, 0.3)',
        }}
      />

      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* 标题：英文大写 + 中文小字 */}
          <div className="flex items-center gap-2 mb-2">
            <p
              className="text-xs font-semibold tracking-wider"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#00f2ff',
                letterSpacing: '0.1em',
              }}
            >
              {title}
            </p>
            {Icon && <Icon className="w-3 h-3" style={{ color: colorValue, opacity: 0.6 }} />}
          </div>
          <p
            className="text-xs mb-3"
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              color: '#71717a',
            }}
          >
            {label}
          </p>

          {/* 数值：等宽字体 + 霓虹光效 */}
          <div
            className="flex items-baseline gap-2 mb-2"
            style={{
              fontFamily: '"DIN Alternate", "JetBrains Mono", monospace',
              fontSize: '32px',
              fontWeight: 500,
              color: value === null ? '#52525b' : '#fafafa',
              lineHeight: 1,
              textShadow: value !== null ? `0 0 20px ${colorValue}40` : 'none',
            }}
          >
            {formatValue(value, unit)}
          </div>

          {/* 微型趋势图 */}
          {sparkline && <div className="mb-2">{sparkline}</div>}

          {/* 描述 */}
          {description && (
            <p
              className="text-xs"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#52525b',
                letterSpacing: '0.02em',
              }}
            >
              {description}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
