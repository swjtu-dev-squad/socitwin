import { Badge } from '@/components/ui';

export function AgentDeepMonitor({ agent }: any) {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 border-b border-border-default pb-4">
        <div className="w-12 h-12 bg-accent/20 rounded-full flex items-center justify-center text-xl">🤖</div>
        <div>
          <h3 className="font-bold text-lg">{agent.name}</h3>
          <Badge variant="outline" className="text-[10px]">{agent.role}</Badge>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">Agent 属性</h4>
        <div className="grid grid-cols-2 gap-4">
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">职业</p>
              <p className="text-sm font-bold text-text-primary">{agent.occupation || '未知'}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">地址</p>
              <p className="text-sm font-bold text-text-primary">{agent.location || '未知'}</p>
           </div>
        </div>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
           <p className="text-[9px] text-text-muted font-bold mb-2">兴趣</p>
           <div className="flex flex-wrap gap-2">
             {agent.interests?.map((interest: string, idx: number) => (
               <Badge key={idx} variant="outline" className="text-[10px] bg-bg-secondary">{interest}</Badge>
             )) || <span className="text-xs text-text-tertiary">无</span>}
           </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">当前话题观点</h4>
        <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20">
           <p className="text-sm font-bold text-blue-400">{agent.recentOpinion || '暂无观点'}</p>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">社交核心指标</h4>
        <div className="grid grid-cols-2 gap-4">
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">影响力 (Influence)</p>
              <p className="text-xl font-mono text-rose-500">{agent.influence}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">活跃度 (Activity)</p>
              <p className="text-xl font-mono text-emerald-500">{agent.activity}%</p>
           </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">当前实时动作</h4>
        <div className="p-4 bg-accent/5 border border-accent/20 rounded-xl">
           <p className="text-xs font-bold text-accent mb-1">{agent.lastAction?.type}</p>
           <p className="text-sm text-text-primary italic">"{agent.lastAction?.content}"</p>
           <div className="mt-3 pt-3 border-t border-accent/10">
              <p className="text-[10px] text-text-muted">决策原因:</p>
              <p className="text-[11px] text-text-secondary">{agent.lastAction?.reason}</p>
           </div>
        </div>
      </div>
    </div>
  );
}
