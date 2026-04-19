import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Badge } from '@/components/ui';
import type { AgentOverview } from '@/lib/agentMonitorTypes';
import { displayMetric, displayPercentage } from '@/lib/safeDisplay';
import { cn } from '@/lib/utils';

export function AgentBehaviorTable({
  agents,
  onSelect,
  selectedId,
}: {
  agents: AgentOverview[];
  onSelect?: (agent: AgentOverview) => void;
  selectedId?: string | null;
}) {
  const rows = agents.map((agent) => ({
    ...agent,
    memoryDisplay: getAgentMemoryDisplay(agent.memory),
  }));

  return (
    <div className="h-full overflow-auto custom-scrollbar">
      <Table className="table-fixed">
        <TableHeader className="sticky top-0 bg-bg-secondary z-10">
          <TableRow className="border-border-default hover:bg-transparent">
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">Agent</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">角色</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">影响力</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">活跃度</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">最近动作</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">动作内容</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">记忆长度</TableHead>
            <TableHead className="h-10 px-3 text-text-tertiary font-bold uppercase text-[10px] tracking-widest">长期记忆</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((agent) => (
            <TableRow 
              key={agent.id} 
              className={cn(
                "border-border-default hover:bg-bg-tertiary/30 transition-colors cursor-pointer",
                selectedId === agent.id && "bg-accent/10 border-l-2 border-l-accent"
              )}
              onClick={() => onSelect?.(agent)}
            >
              <TableCell className="h-12 px-3 py-2 font-bold text-sm truncate">{agent.name}</TableCell>
              <TableCell className="h-12 px-3 py-2">
                <Badge variant="outline" className="text-[10px]">{agent.roleLabel || agent.role}</Badge>
              </TableCell>
              <TableCell className="h-12 px-3 py-2 font-mono text-accent">{displayMetric(agent.influence)}</TableCell>
              <TableCell className="h-12 px-3 py-2 font-mono text-emerald-500">{displayPercentage(agent.activity)}</TableCell>
              <TableCell className="h-12 px-3 py-2">
                <Badge className="bg-bg-tertiary text-text-secondary border-border-default text-[9px]">
                  {agent.lastAction?.type || '-'}
                </Badge>
              </TableCell>
              <TableCell className="h-12 px-3 py-2 text-xs text-text-secondary italic">
                <div className="truncate">{agent.lastAction?.content || agent.actionContent || '-'}</div>
              </TableCell>
              <TableCell className="h-12 px-3 py-2 font-mono text-accent">
                {formatMemoryLength(agent.memory?.length)}
              </TableCell>
              <TableCell className="h-12 px-3 py-2">
                <div className="space-y-1" title={agent.memoryDisplay.title}>
                  <div className="flex flex-wrap items-center gap-1">
                    <Badge className={cn('text-[9px] border', agent.memoryDisplay.stageClassName)}>
                      {agent.memoryDisplay.stageLabel}
                    </Badge>
                    {agent.memoryDisplay.countLabel ? (
                      <Badge className="text-[9px] border border-border-default bg-bg-tertiary text-text-secondary">
                        {agent.memoryDisplay.countLabel}
                      </Badge>
                    ) : null}
                    {agent.memoryDisplay.sourceLabel ? (
                      <Badge className="text-[9px] border border-sky-500/20 bg-sky-500/10 text-sky-300">
                        {agent.memoryDisplay.sourceLabel}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="line-clamp-2 text-[11px] leading-4 text-text-secondary">
                    {agent.memoryDisplay.detail}
                  </div>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function formatMemoryLength(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : '-';
}

function getAgentMemoryDisplay(memory: AgentOverview['memory'] | null | undefined) {
  const retrieval = memory?.retrieval;
  const debug = memory?.debug;
  const recalledCount = safeCount(debug?.lastRecalledCount);
  const injectedCount = safeCount(debug?.lastInjectedCount);
  const recalledStepIds = normalizeIds(debug?.lastRecalledStepIds);
  const injectedStepIds = normalizeIds(debug?.lastInjectedStepIds);
  const querySource = formatRecallQuerySource(debug?.lastRecallQuerySource);

  if (!retrieval?.enabled) {
    return {
      stageLabel: '未启用',
      countLabel: null,
      sourceLabel: null,
      detail: '当前路线不使用长期记忆',
      title: '当前路线未启用长期记忆召回。',
      stageClassName: 'border-border-default bg-bg-tertiary text-text-tertiary',
    };
  }

  if (retrieval.status === 'error') {
    const failureStage = formatFailureStage(
      debug?.lastRuntimeFailureCategory,
      debug?.lastRuntimeFailureStage,
    );
    return {
      stageLabel: '异常',
      countLabel: null,
      sourceLabel: null,
      detail: failureStage,
      title: `长期记忆异常：${failureStage}`,
      stageClassName: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    };
  }

  if (injectedCount > 0) {
    const detail = [
      `已将 ${injectedCount} 条长期记忆注入本轮 prompt`,
      recalledCount > injectedCount ? `，共召回 ${recalledCount} 条候选` : '',
    ].join('');
    return {
      stageLabel: '已注入',
      countLabel: `${injectedCount}/${Math.max(recalledCount, injectedCount)} 条`,
      sourceLabel: querySource,
      detail,
      title: [
        `长期记忆已注入：${injectedCount} 条`,
        recalledCount > 0 ? `召回候选：${recalledCount} 条` : '',
        injectedStepIds.length > 0 ? `注入步次：${injectedStepIds.join(', ')}` : '',
        querySource ? `查询来源：${querySource}` : '',
      ].filter(Boolean).join('\n'),
      stageClassName: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    };
  }

  if (recalledCount > 0) {
    return {
      stageLabel: '已召回',
      countLabel: `${recalledCount} 条`,
      sourceLabel: querySource,
      detail: '已找到长期记忆候选，但本轮未注入 prompt',
      title: [
        `长期记忆已召回：${recalledCount} 条`,
        recalledStepIds.length > 0 ? `召回步次：${recalledStepIds.join(', ')}` : '',
        querySource ? `查询来源：${querySource}` : '',
      ].filter(Boolean).join('\n'),
      stageClassName: 'border-sky-500/30 bg-sky-500/10 text-sky-300',
    };
  }

  if (retrieval.status === 'empty' || debug?.lastRecallGate === true) {
    return {
      stageLabel: '未命中',
      countLabel: '0 条',
      sourceLabel: querySource,
      detail: '本轮触发了长期记忆检索，但没有找到可注入候选',
      title: [
        '本轮已触发长期记忆检索，但没有命中可注入候选。',
        querySource ? `查询来源：${querySource}` : '',
      ].filter(Boolean).join('\n'),
      stageClassName: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    };
  }

  return {
    stageLabel: '未触发',
    countLabel: null,
    sourceLabel: querySource,
    detail: '本轮没有进入长期记忆召回阶段',
    title: [
      '本轮没有进入长期记忆召回阶段。',
      querySource ? `最近一次查询来源：${querySource}` : '',
    ].filter(Boolean).join('\n'),
    stageClassName: 'border-border-default bg-bg-tertiary text-text-tertiary',
  };
}

function safeCount(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function normalizeIds(values: number[] | null | undefined) {
  if (!Array.isArray(values)) return [];
  return values.filter((value) => typeof value === 'number' && Number.isFinite(value));
}

function formatRecallQuerySource(value: string | null | undefined) {
  const normalized = String(value ?? '').trim();
  if (!normalized) return null;

  const labels: Record<string, string> = {
    distilled_topic: '主题',
    structured_event_query: '事件',
    recent_episodic_summary: '近况',
  };

  return labels[normalized] || normalized;
}

function formatFailureStage(category: string | null | undefined, stage: string | null | undefined) {
  const normalizedCategory = String(category ?? '').trim();
  const normalizedStage = String(stage ?? '').trim();

  if (normalizedCategory && normalizedStage) {
    return `${normalizedCategory} / ${normalizedStage}`;
  }
  return normalizedCategory || normalizedStage || '长期记忆暂不可用';
}
