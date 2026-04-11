import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, Badge } from '@/components/ui';
import type { AgentOverview } from '@/lib/agentMonitorTypes';
import { getDisplayMemoryContent } from '@/lib/agentMemoryDisplay';
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
    displayMemoryContent: getDisplayMemoryContent(agent.memory?.content) || '-',
  }));

  return (
    <div className="h-full overflow-auto custom-scrollbar">
      <Table>
        <TableHeader className="sticky top-0 bg-bg-secondary z-10">
          <TableRow className="border-border-default hover:bg-transparent">
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">Agent</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">角色</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">影响力</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">活跃度</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">最近动作</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">动作内容</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">记忆长度</TableHead>
            <TableHead className="text-text-tertiary font-bold uppercase text-[10px] tracking-widest">记忆内容</TableHead>
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
              <TableCell className="font-bold text-sm">{agent.name}</TableCell>
              <TableCell>
                <Badge variant="outline" className="text-[10px]">{agent.roleLabel || agent.role}</Badge>
              </TableCell>
              <TableCell className="font-mono text-accent">{agent.influence}</TableCell>
              <TableCell className="font-mono text-emerald-500">{agent.activity}%</TableCell>
              <TableCell>
                <Badge className="bg-bg-tertiary text-text-secondary border-border-default text-[9px]">
                  {agent.lastAction?.type || '-'}
                </Badge>
              </TableCell>
              <TableCell className="text-xs text-text-secondary italic max-w-xs truncate">
                {agent.lastAction?.content || agent.actionContent || '-'}
              </TableCell>
              <TableCell className="font-mono text-accent">
                {formatMemoryLength(agent.memory?.length)}
              </TableCell>
              <TableCell className="max-w-[18rem]">
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
