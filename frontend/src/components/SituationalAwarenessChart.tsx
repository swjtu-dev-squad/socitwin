import { useMemo } from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts'
import { useSimulationStore } from '@/lib/store'
import { useMetricsHistory } from '@/hooks/useSimulationData'
import { Activity } from 'lucide-react'

interface SituationalAwarenessChartProps {
  currentStep: number
}

export const SituationalAwarenessChart = ({ currentStep }: SituationalAwarenessChartProps) => {
  const { status } = useSimulationStore()
  const { data: chartHistory } = useMetricsHistory(currentStep)

  // 准备历史趋势数据（从数据库读取，step-based）
  const trendData = useMemo(() => {
    if (!chartHistory || chartHistory.length === 0) return []

    const data = chartHistory.map(h => ({
      step: h.step,
      极化: h.polarization || 0,
      从众: h.herdEffect || 0,
      传播: Math.min((h.propagation || 0) / Math.max(status.activeAgents || 1, 1), 1),
    }))

    console.log('📈 [SituationalAwarenessChart] trendData:', data)
    return data
  }, [chartHistory, status.activeAgents])

  return (
    <div className="w-full">
      {/* 多指标耦合动态趋势图 */}
      <div className="flex flex-col" style={{ position: 'relative' }}>
        {/* 标题区域 */}
        <div
          className="flex justify-between items-center mb-6 pb-4"
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
              width: '100px',
              height: '2px',
              background: 'linear-gradient(90deg, #00f2ff 0%, rgba(0, 242, 255, 0.3) 100%)',
            }}
          />

          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4" style={{ color: '#00f2ff', opacity: 0.8 }} />
            <h3
              className="text-xs font-bold uppercase tracking-widest"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#00f2ff',
                letterSpacing: '0.15em',
              }}
            >
              多指标耦合动态
            </h3>
          </div>

          <div className="flex gap-3">
            <span
              className="flex items-center gap-2 text-[10px] font-semibold"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#f43f5e',
                letterSpacing: '0.05em',
              }}
            >
              <div className="w-1.5 h-1.5" style={{ background: '#f43f5e' }} /> 极化
            </span>
            <span
              className="flex items-center gap-2 text-[10px] font-semibold"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#10b981',
                letterSpacing: '0.05em',
              }}
            >
              <div className="w-1.5 h-1.5" style={{ background: '#10b981' }} /> 传播
            </span>
            <span
              className="flex items-center gap-2 text-[10px] font-semibold"
              style={{
                fontFamily: '"JetBrains Mono", monospace',
                color: '#00f2ff',
                letterSpacing: '0.05em',
              }}
            >
              <div className="w-1.5 h-1.5" style={{ background: '#00f2ff' }} /> 从众
            </span>
          </div>
        </div>

        {/* 图表区域 */}
        <div className="flex-1 w-full" style={{ minHeight: '350px', height: '350px' }}>
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={trendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorPol" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorProp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorHerd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00f2ff" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#00f2ff" stopOpacity={0} />
                </linearGradient>
              </defs>

              {/* 科技风网格 - 虚线 */}
              <CartesianGrid
                strokeDasharray="2 2"
                stroke="rgba(0, 242, 255, 0.1)"
                vertical={true}
                horizontal={true}
              />

              {/* X轴 - 细线 */}
              <XAxis
                dataKey="step"
                stroke="rgba(113, 113, 122, 0.5)"
                fontSize={10}
                fontFamily='"JetBrains Mono", monospace'
                tickFormatter={value => `STEP ${value}`}
                tick={{ fill: '#71717a' }}
              />

              {/* Y轴 - 细线 */}
              <YAxis
                stroke="rgba(113, 113, 122, 0.5)"
                fontSize={10}
                fontFamily='"JetBrains Mono", monospace'
                domain={[0, 1]}
                tickCount={5}
                tickFormatter={value => `${(value * 100).toFixed(0)}%`}
                tick={{ fill: '#71717a' }}
              />

              {/* 科技风 Tooltip */}
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(24, 30, 37, 0.95)',
                  border: '1px solid rgba(0, 242, 255, 0.3)',
                  borderRadius: '2px',
                  fontFamily: '"JetBrains Mono", monospace',
                  fontSize: '12px',
                  color: '#fafafa',
                  boxShadow: '0 0 20px rgba(0, 242, 255, 0.2)',
                }}
                labelStyle={{
                  color: '#71717a',
                  fontSize: '11px',
                }}
                itemStyle={{
                  padding: '4px 8px',
                }}
                formatter={(value: any, name: any) => {
                  if (name === 'step') return `STEP ${value}`
                  return `${((value || 0) * 100).toFixed(1)}%`
                }}
              />

              {/* 极化 - 玫瑰红 */}
              <Area
                type="monotone"
                dataKey="极化"
                stroke="#f43f5e"
                fillOpacity={1}
                fill="url(#colorPol)"
                strokeWidth={1.5}
                dot={false}
              />

              {/* 传播 - 翠翠绿 */}
              <Area
                type="monotone"
                dataKey="传播"
                stroke="#10b981"
                fillOpacity={1}
                fill="url(#colorProp)"
                strokeWidth={1.5}
                dot={false}
              />

              {/* 从众 - 电光蓝 */}
              <Area
                type="monotone"
                dataKey="从众"
                stroke="#00f2ff"
                fillOpacity={1}
                fill="url(#colorHerd)"
                strokeWidth={1.5}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* 说明文字 */}
        <p
          className="text-[10px] mt-4"
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            color: '#52525b',
            letterSpacing: '0.02em',
          }}
        >
          * 基于数据库历史数据绘制 · X轴为模拟步数 · 指标已归一化处理
        </p>

        {/* 装饰性角标 */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            right: 0,
            width: '8px',
            height: '8px',
            borderBottom: '1px solid rgba(0, 242, 255, 0.3)',
            borderRight: '1px solid rgba(0, 242, 255, 0.3)',
          }}
        />
      </div>
    </div>
  )
}
