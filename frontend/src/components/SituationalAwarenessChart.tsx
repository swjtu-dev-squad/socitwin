import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { useSimulationStore } from '@/lib/store';
import { Card } from '@/components/ui';
import { Activity, Target } from 'lucide-react';

export const SituationalAwarenessChart = () => {
  const { status, history } = useSimulationStore();

  // 1. 准备雷达图数据（当前快照）
  // 传播规模：使用参与互动的用户数比例（propagation.scale / activeAgents）
  const radarData = useMemo(() => {
    const normPropagation = Math.min(
      ((status.propagation?.scale || 0) / Math.max(status.activeAgents || 1, 1)),
      1
    );
    return [
      { subject: '群体极化 (Polarization)', value: status.polarization || 0, fullMark: 1 },
      { subject: '信息传播 (Propagation)', value: normPropagation, fullMark: 1 },
      { subject: '从众效应 (Conformity)', value: status.herdHhi || 0, fullMark: 1 },
    ];
  }, [status]);

  // 2. 准备历史趋势数据（归一化）
  const trendData = useMemo(() => {
    return history.map((h) => ({
      time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      极化: h.polarization,
      从众: h.herdHhi || 0,
      传播: Math.min(
        ((h.propagation?.scale || 0) / Math.max((h.activeAgents || status.activeAgents || 1), 1)),
        1
      ), // 归一化显示：参与互动的用户比例
    }));
  }, [history, status.activeAgents]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 w-full h-full min-h-[450px]">
      
      {/* 左侧：多维态势雷达图 */}
      <Card className="lg:col-span-1 p-6 bg-bg-secondary border-border-default flex flex-col items-center justify-center relative overflow-hidden">
        <div className="absolute top-4 left-4 flex items-center gap-2">
          <Target className="w-4 h-4 text-accent" />
          <h3 className="text-xs font-bold uppercase tracking-widest text-text-secondary">实时系统态势</h3>
        </div>
        
        <div className="w-full h-[300px] mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
              <PolarGrid stroke="#24201E" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#71717a', fontSize: 10 }} />
              <Radar
                name="当前状态"
                dataKey="value"
                stroke="#10b981"
                fill="#10b981"
                fillOpacity={0.5}
              />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0D0D0D', border: '1px solid #24201E', borderRadius: '8px' }}
                itemStyle={{ fontSize: '12px' }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="flex gap-4 mt-2">
          <div className="flex flex-col items-center">
            <span className="text-[10px] text-text-tertiary uppercase font-bold">系统熵值</span>
            <span className="text-lg font-mono text-white">{(status.polarization * status.herdHhi * 10).toFixed(2)}</span>
          </div>
          <div className="w-[1px] h-8 bg-border-default"></div>
          <div className="flex flex-col items-center">
            <span className="text-[10px] text-text-tertiary uppercase font-bold">联动指数</span>
            <span className="text-lg font-mono text-accent">{((status.propagation?.scale || 0) / Math.max(status.activeAgents || 1, 1)).toFixed(2)}</span>
          </div>
        </div>
      </Card>

      {/* 右侧：三位一体趋势图 */}
      <Card className="lg:col-span-2 p-6 bg-bg-secondary border-border-default flex flex-col">
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
              <XAxis dataKey="time" hide />
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
          * 指标已归一化处理。当三条曲线高度重合时，系统正处于极高风险的“共振”状态。
        </p>
      </Card>
    </div>
  );
};
