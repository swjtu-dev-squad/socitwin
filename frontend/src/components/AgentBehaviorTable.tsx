import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Badge } from '@/components/ui';
import type { AgentOverview } from '@/lib/agentMonitorTypes';
import { getDisplayMemoryContent } from '@/lib/agentMemoryDisplay';
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
    displayMemoryContent: getAgentMemoryDisplay(agent.memory),
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
                <div
                  className="truncate text-xs text-text-secondary italic"
                  title={agent.displayMemoryContent}
                >
                  {agent.displayMemoryContent}
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

  if (!retrieval) {
    return getDisplayMemoryContent(memory?.content) || '-';
  }

  if (retrieval.status === 'empty') {
    return '已检索，无可注入记忆';
  }

  if (retrieval.status === 'error') {
    return '长期记忆暂不可用';
  }

  if (retrieval.status === 'ready') {
    const retrievalContent = summarizeMemoryContent(retrieval.content);
    if (retrievalContent) {
      return retrievalContent;
    }

    const firstItemContent = retrieval.items.find((item) => summarizeMemoryContent(item.content))?.content;
    if (firstItemContent) {
      return `Long-term memory: ${summarizeMemoryContent(firstItemContent)}`;
    }

    return 'Long-term memory ready';
  }

  const query = memory?.debug?.lastRecallQueryText;
  if (query) {
    return `待召回：${query}`;
  }

  return getDisplayMemoryContent(memory?.content) || '尚未触发长期记忆';
}

function summarizeMemoryContent(value: string | null | undefined) {
  const normalized = String(value ?? '').replace(/\r\n/g, '\n').trim();
  if (!normalized) return '';

  const lines = normalized
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) return '';
  if (lines.length === 1) return lines[0].replace(/^[-*•]\s*/, '');

  const [first, second] = lines;
  if (/^Long-term memory/i.test(first)) {
    return `Long-term memory: ${second.replace(/^[-*•]\s*/, '')}`;
  }

  return first.replace(/^[-*•]\s*/, '');
}
