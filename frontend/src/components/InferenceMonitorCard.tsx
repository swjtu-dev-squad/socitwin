import React from 'react'
import { LineChart, Line, ResponsiveContainer } from 'recharts'
import type { InferenceTask } from '@/lib/labTypes'

interface InferenceMonitorCardProps {
  task: InferenceTask
}

export const InferenceMonitorCard: React.FC<InferenceMonitorCardProps> = ({ task }) => {
  return (
    <div className="bg-bg-secondary border border-border-default rounded-2xl p-5 space-y-4">
      <div className="flex justify-between items-start">
        <div>
          <h3 className="font-bold text-text-primary">{task.name}</h3>
          <p className="text-xs text-text-tertiary">参照基准: {task.baselineId}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-bold text-text-tertiary uppercase">拟合度 (Accuracy)</p>
          <p className="text-2xl font-mono font-bold text-emerald-400">{task.metrics.fitScore}%</p>
        </div>
      </div>

      {/* 实时趋势对标小图表 */}
      <div className="h-24 w-full bg-bg-primary/50 rounded-lg p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={task.stepsTrace}>
            <Line
              type="monotone"
              dataKey="simValue"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              name="模拟"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="baseValue"
              stroke="#71717a"
              strokeDasharray="3 3"
              dot={false}
              name="基准"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border-default">
        <div>
          <p className="text-[9px] text-text-muted font-bold uppercase">极化率 (模拟/基准)</p>
          <p className="font-mono text-sm text-text-secondary">
            {task.metrics.currentPolarization} / {task.metrics.baselinePolarization}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[9px] text-text-muted font-bold uppercase">预测偏差 (Bias)</p>
          <p className="font-mono text-sm text-rose-400">
            {task.metrics.biasValue > 0 ? '+' : ''}
            {task.metrics.biasValue}%
          </p>
        </div>
      </div>
    </div>
  )
}
