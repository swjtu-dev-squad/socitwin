import { useMemo } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { useSimulationStore } from '@/lib/store';
import { useMetricsHistory } from '@/hooks/useSimulationData';
import { Card } from '@/components/ui';
import { Activity } from 'lucide-react';

interface SituationalAwarenessChartProps {
  currentStep: number;
}

export const SituationalAwarenessChart = ({ currentStep }: SituationalAwarenessChartProps) => {
  const { status } = useSimulationStore();
  const { data: chartHistory } = useMetricsHistory(currentStep);

  // 准备历史趋势数据（从数据库读取，step-based）
  const trendData = useMemo(() => {
    if (!chartHistory || chartHistory.length === 0) return [];

    return chartHistory.map((h) => ({
      step: h.step,
      极化: h.polarization || 0,
      从众: h.herdEffect || 0,
      传播: Math.min((h.propagation || 0) / Math.max((status.activeAgents || 1), 1), 1),
    }));
  }, [chartHistory, status.activeAgents]);

  return (
    <div className="grid grid-cols-1 gap-6 w-full h-full min-h-[450px]">
      {/* 多指标耦合动态趋势图 */}
      <Card className="p-6 bg-bg-secondary border-border-default flex flex-col">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-500" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-text-secondary">多指标耦合动态</h3>
          </div>
          <div className="flex gap-2">
             <span className="flex items-center gap-1 text-[10px] font-bold text-rose-500"><div className="w-2 h-2 rounded-full bg-rose-500"/> 极化</span>
             <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-500"><div className="w-2 h-2 rounded-full bg-emerald-500"/> 传播</span>
             <span className="flex items-center gap-1 text-[10px] font-bold text-blue-500"><div className="w-2 h-2 rounded-full bg-blue-500"/> 从众</span>
          </div>
        </div>

        <div className="flex-1 w-full min-h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trendData}>
              <defs>
                <linearGradient id="colorPol" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorProp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorHerd" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#24201E" vertical={false} />
              <XAxis dataKey="step" stroke="#1A1614" fontSize={10} />
              <YAxis stroke="#1A1614" fontSize={10} domain={[0, 1]} tickCount={5} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0D0D0D', border: '1px solid #24201E', borderRadius: '12px' }}
              />
              <Area type="monotone" dataKey="极化" stroke="#f43f5e" fillOpacity={1} fill="url(#colorPol)" strokeWidth={2} />
              <Area type="monotone" dataKey="传播" stroke="#10b981" fillOpacity={1} fill="url(#colorProp)" strokeWidth={2} />
              <Area type="monotone" dataKey="从众" stroke="#3b82f6" fillOpacity={1} fill="url(#colorHerd)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <p className="text-[10px] text-text-tertiary mt-4 italic">
          * 指标已归一化处理，基于数据库历史数据绘制。X轴为模拟步数。
        </p>
      </Card>
    </div>
  );
};
