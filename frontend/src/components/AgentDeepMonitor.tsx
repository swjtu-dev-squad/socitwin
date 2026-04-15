import { Badge } from '@/components/ui';
import { getDisplayMemoryContent } from '@/lib/agentMemoryDisplay';
import type { AgentDetailResponse, AgentMemorySnapshot } from '@/lib/agentMonitorTypes';
import { displayMetric, displayPercentage, displayCount } from '@/lib/safeDisplay';

type AgentDeepMonitorProps = {
  detail: AgentDetailResponse | null;
  loading?: boolean;
  error?: string | null;
};

export function AgentDeepMonitor({ detail, loading = false, error = null }: AgentDeepMonitorProps) {
  if (loading) {
    return <StatePanel title="正在加载 Agent 详情" description="请稍候，正在从数据库获取真实数据。" />;
  }

  if (error) {
    return <StatePanel title="加载失败" description={error} tone="error" />;
  }

  if (!detail) {
    return <StatePanel title="请选择一个 Agent" description="点击左侧图谱节点或表格行查看详细数据。" />;
  }

  const { profile, status, currentViewpoint, lastAction, recentTimeline, seenPosts } = detail;
  const memory = detail.memory ?? getEmptyMemorySnapshot();
  const retrieval = memory.retrieval ?? getEmptyRetrieval();
  const memoryContent = getMemoryContent(memory, retrieval);
  const memoryItems = Array.isArray(retrieval.items) ? retrieval.items : [];
  const debug = memory.debug ?? {};

  return (
    <div className="space-y-6">
      {/* 头部：基本信息 */}
      <div className="flex items-center gap-4 border-b border-border-default pb-4">
        <div className="w-12 h-12 bg-accent/20 rounded-full flex items-center justify-center text-xl">🤖</div>
        <div>
          <h3 className="font-bold text-lg">{profile.name}</h3>
          <p className="text-xs text-text-tertiary">@{profile.user_name || profile.id}</p>
        </div>
      </div>

      {/* 档案信息 */}
      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">档案信息</h4>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">个人简介</p>
          <p className="text-sm text-text-primary leading-relaxed">{profile.bio || '暂无简介'}</p>
        </div>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">兴趣标签</p>
          <div className="flex flex-wrap gap-2">
            {profile.tags?.length ? profile.tags.map((interest, idx) => (
              <Badge key={idx} variant="outline" className="text-[10px] bg-bg-secondary">{interest}</Badge>
            )) : <span className="text-xs text-text-tertiary">无</span>}
          </div>
        </div>
      </div>

      {/* 长短期记忆状态 */}
      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">记忆与召回</h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">模式</p>
            <p className="text-sm font-bold text-text-primary">{debug.memoryMode || '-'}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">Prompt Tokens</p>
            <p className="text-xl font-mono text-accent">{formatMemoryLength(memory.length)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">召回状态</p>
            <Badge variant="outline" className="text-[10px]">{retrieval.status}</Badge>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">召回条目</p>
            <p className="text-sm font-mono text-text-primary">
              {displayCount(debug.lastInjectedCount ?? memoryItems.length)} / {displayCount(debug.lastRecalledCount ?? memoryItems.length)}
            </p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">Recent 保留</p>
            <p className="text-sm font-mono text-text-primary">
              {displayCount(debug.recentRetainedStepCount ?? (debug.recentRetainedStepIds || []).length)}
            </p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">Compressed 保留</p>
            <p className="text-sm font-mono text-text-primary">{displayCount(debug.compressedRetainedStepCount)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">本轮 Recent</p>
            <p className="text-sm font-mono text-text-primary">{displayCount((debug.lastSelectedRecentStepIds || []).length)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">本轮 Compressed</p>
            <p className="text-sm font-mono text-text-primary">{displayCount((debug.lastSelectedCompressedKeys || []).length)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">本轮 Recall</p>
            <p className="text-sm font-mono text-text-primary">{displayCount((debug.lastSelectedRecallStepIds || []).length)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">观察 Tokens</p>
            <p className="text-sm font-mono text-text-primary">{displayCount(debug.lastObservationPromptTokens)}</p>
          </div>
        </div>

        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">本轮 Prompt 记忆构成</p>
          <div className="grid grid-cols-3 gap-2 text-[11px] text-text-secondary">
            <MemoryIdList label="Recent" values={debug.lastSelectedRecentStepIds} />
            <MemoryIdList label="Compressed" values={debug.lastSelectedCompressedKeys} />
            <MemoryIdList label="Recall" values={debug.lastSelectedRecallStepIds} />
          </div>
        </div>

        {debug.lastRecallQueryText ? (
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold mb-2">召回查询</p>
            <p className="text-sm text-text-primary whitespace-pre-wrap break-words leading-6">{debug.lastRecallQueryText}</p>
          </div>
        ) : null}

        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">
            {retrieval.status === 'ready'
              ? 'Long-term memory recall'
              : retrieval.status === 'empty'
                ? '已检索，无可注入记忆'
                : retrieval.status === 'error'
                  ? '长期记忆暂不可用'
                  : '记忆状态'}
          </p>
          <div className="max-h-36 overflow-auto rounded-lg border border-border-default bg-bg-secondary/80 p-3">
            <p className="text-sm text-text-primary whitespace-pre-wrap break-words leading-6">
              {memoryContent || '-'}
            </p>
          </div>
        </div>

        <div className="p-3 bg-bg-primary rounded-xl border border-border-default space-y-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[9px] text-text-muted font-bold">召回条目</p>
            <Badge variant="outline" className="text-[10px]">{memoryItems.length}</Badge>
          </div>
          <div className="max-h-52 overflow-auto space-y-2 pr-1">
            {memoryItems.length > 0 ? memoryItems.map((item) => (
              <div key={item.id} className="rounded-lg border border-border-default bg-bg-secondary/80 p-3">
                <p className="text-sm text-text-primary whitespace-pre-wrap break-words leading-6">{item.content || '-'}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-text-tertiary">
                  <span>{formatMemoryItemStep(item.createdAt)}</span>
                  {typeof item.score === 'number' && Number.isFinite(item.score) ? <span>score {item.score.toFixed(2)}</span> : null}
                  {item.source ? <span>{item.source}</span> : null}
                </div>
              </div>
            )) : (
              <p className="text-sm text-text-tertiary">暂无召回条目</p>
            )}
          </div>
        </div>
      </div>

      {/* 当前话题观点 */}
      {currentViewpoint && (
        <div className="space-y-4">
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">当前话题观点</h4>
          <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20">
             <p className="text-sm font-bold text-blue-400">{currentViewpoint}</p>
          </div>
        </div>
      )}

      {/* 社交核心指标 */}
      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">社交核心指标</h4>
        <div className="grid grid-cols-2 gap-4">
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">影响力</p>
              <p className="text-xl font-mono text-accent">{displayMetric(status.influence)}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">活跃度</p>
              <p className="text-xl font-mono text-emerald-500">{displayPercentage(status.activity)}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">关注 / 粉丝</p>
              <p className="text-sm font-mono text-text-primary">{status.followingCount} / {status.followerCount}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">交互次数</p>
              <p className="text-sm font-mono text-text-primary">{displayCount(status.interactionCount)}</p>
           </div>
        </div>
      </div>

      {/* 最近帖子 */}
      {seenPosts.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">最近帖子</h4>
          <div className="space-y-3">
            {seenPosts.slice(0, 3).map((post) => (
              <div key={post.postId} className="p-3 bg-bg-primary rounded-xl border border-border-default">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[10px] text-text-tertiary">{post.author}</span>
                  <span className="text-[10px] text-text-tertiary">{formatTime(post.timestamp)}</span>
                </div>
                <p className="mt-2 text-sm text-text-primary leading-relaxed">{post.content}</p>
                {post.numLikes !== undefined && (
                  <p className="mt-1 text-[11px] text-text-muted">❤️ {post.numLikes}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 当前实时动作 */}
      {lastAction && (
        <div className="space-y-4">
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">最新动作</h4>
          <div className="p-4 bg-accent/5 border border-accent/20 rounded-xl">
             <p className="text-xs font-bold text-accent mb-1">{lastAction.type}</p>
             <p className="text-sm text-text-primary italic">"{lastAction.content || '-'}"</p>
             {lastAction.reason && (
               <div className="mt-3 pt-3 border-t border-accent/10">
                  <p className="text-[10px] text-text-muted">决策原因:</p>
                  <p className="text-[11px] text-text-secondary">{lastAction.reason}</p>
               </div>
             )}
          </div>
        </div>
      )}

      {/* 最近轨迹 */}
      {recentTimeline.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">行为轨迹</h4>
          <div className="space-y-3 max-h-80 overflow-auto">
            {recentTimeline.slice(0, 10).map((item, idx) => (
              <div key={`${item.timestamp}-${item.type}-${idx}`} className="p-3 bg-bg-primary rounded-xl border border-border-default">
                <div className="flex items-center justify-between gap-3">
                  <Badge variant="outline" className="text-[10px]">{item.type}</Badge>
                  <span className="text-[10px] text-text-tertiary">{formatTime(item.timestamp)}</span>
                </div>
                {item.content && <p className="mt-2 text-sm text-text-primary">{item.content}</p>}
                {item.reason && <p className="mt-1 text-[11px] text-text-muted">{item.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatePanel({ title, description, tone = 'default' }: { title: string; description: string; tone?: 'default' | 'error' }) {
  return (
    <div className="h-full min-h-[360px] flex flex-col items-center justify-center text-center px-6">
      <div className={tone === 'error' ? 'text-rose-400' : 'text-text-muted'}>
        <div className="w-14 h-14 rounded-full border border-border-default bg-bg-primary flex items-center justify-center mb-4 mx-auto text-xl">
          {tone === 'error' ? '!' : '↺'}
        </div>
        <h3 className="text-lg font-bold text-text-primary">{title}</h3>
        <p className="mt-2 text-sm text-text-tertiary max-w-xs">{description}</p>
      </div>
    </div>
  );
}

function getEmptyRetrieval(): AgentMemorySnapshot['retrieval'] {
  return {
    length: 0,
    enabled: false,
    status: 'not_configured',
    content: '',
    items: [],
  };
}

function getEmptyMemorySnapshot(): AgentMemorySnapshot {
  return {
    length: 0,
    content: '',
    contentSource: 'system_prompt',
    systemPrompt: {
      length: 0,
      content: '',
    },
    retrieval: getEmptyRetrieval(),
    debug: {},
  };
}

function getMemoryContent(memory: AgentMemorySnapshot, retrieval: AgentMemorySnapshot['retrieval']) {
  if (retrieval.status === 'empty') {
    return '本轮触发长期记忆检索，但没有可注入的召回结果。';
  }

  if (retrieval.status === 'error') {
    return retrieval.content || '长期记忆暂不可用';
  }

  if (retrieval.status === 'ready') {
    const retrievalContent = normalizeDisplayContent(retrieval.content);
    if (retrievalContent) {
      return retrievalContent;
    }

    const itemContent = retrieval.items
      .map((item) => normalizeDisplayContent(item.content))
      .filter(Boolean);

    if (itemContent.length > 0) {
      return `Long-term memory:\n${itemContent.map((content) => `- ${content}`).join('\n')}`;
    }

    return 'Long-term memory ready';
  }

  return retrieval.content || getDisplayMemoryContent(memory.content) || '尚未触发长期记忆召回';
}

function normalizeDisplayContent(value: string | null | undefined) {
  return String(value ?? '').replace(/\r\n/g, '\n').trim();
}

function formatMemoryItemStep(value: string | null | undefined) {
  const normalized = normalizeDisplayContent(value);
  if (!normalized) return 'step -';
  return /^\d+$/.test(normalized) ? `step ${normalized}` : normalized;
}

function formatMemoryLength(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : '-';
}

function MemoryIdList({ label, values }: { label: string; values?: Array<number | string> }) {
  const items = values || [];
  return (
    <div className="rounded-lg border border-border-default bg-bg-secondary/70 p-2 min-w-0">
      <p className="text-[9px] font-bold text-text-muted">{label}</p>
      <p className="mt-1 truncate font-mono text-text-primary" title={items.join(', ')}>
        {items.length > 0 ? items.join(', ') : '-'}
      </p>
    </div>
  );
}

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
