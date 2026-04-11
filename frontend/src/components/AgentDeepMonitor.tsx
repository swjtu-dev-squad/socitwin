import { Badge } from '@/components/ui';
import { getDisplayMemoryContent } from '@/lib/agentMemoryDisplay';
import type { AgentDetailResponse, AgentMemorySnapshot } from '@/lib/agentMonitorTypes';
import { displayMetric, displayPercentage, displayCount, displayText, displayLocation, displayRatio } from '@/lib/safeDisplay';

type AgentDeepMonitorProps = {
  detail: AgentDetailResponse | null;
  loading?: boolean;
  error?: string | null;
};

export function AgentDeepMonitor({ detail, loading = false, error = null }: AgentDeepMonitorProps) {
  if (loading) {
    return <StatePanel title="正在加载 Agent 详情" description="请稍候，正在获取真实画像与轨迹数据。" />;
  }

  if (error) {
    return <StatePanel title="加载失败" description={error} tone="error" />;
  }

  if (!detail) {
    return <StatePanel title="请选择一个 Agent" description="点击左侧图谱节点或表格行查看真实画像与状态。" />;
  }

  const { profile, status, currentViewpoint, lastAction, recentTimeline, seenPosts } = detail;
  const memory = detail.memory ?? getEmptyMemorySnapshot();
  const retrieval = memory.retrieval ?? getEmptyRetrieval();
  const displayMemoryContent = getDisplayMemoryContent(memory.content);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 border-b border-border-default pb-4">
        <div className="w-12 h-12 bg-accent/20 rounded-full flex items-center justify-center text-xl">🤖</div>
        <div>
          <h3 className="font-bold text-lg">{profile.name}</h3>
          <Badge variant="outline" className="text-[10px]">{profile.roleLabel}</Badge>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">Agent 属性</h4>
        <div className="grid grid-cols-2 gap-4">
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">职业</p>
              <p className="text-sm font-bold text-text-primary">{displayText(profile.occupation) || '未知'}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">地址</p>
              <p className="text-sm font-bold text-text-primary">{displayLocation(profile.country, profile.city) || '未知'}</p>
           </div>
        </div>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
           <p className="text-[9px] text-text-muted font-bold mb-2">兴趣</p>
           <div className="flex flex-wrap gap-2">
             {profile.tags?.length ? profile.tags.map((interest, idx) => (
               <Badge key={idx} variant="outline" className="text-[10px] bg-bg-secondary">{interest}</Badge>
             )) : <span className="text-xs text-text-tertiary">无</span>}
           </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">记忆信息</h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">记忆长度</p>
            <p className="text-xl font-mono text-accent">{formatMemoryLength(memory.length)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">当前来源</p>
            <p className="text-sm font-bold text-text-primary">{memory.contentSource || 'system_prompt'}</p>
          </div>
        </div>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">记忆内容</p>
          <div className="max-h-36 overflow-auto rounded-lg border border-border-default bg-bg-secondary/80 p-3">
            <p className="text-sm text-text-primary whitespace-pre-wrap break-words leading-6">
              {displayMemoryContent || '-'}
            </p>
          </div>
        </div>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default space-y-2">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[9px] text-text-muted font-bold">检索占位状态</p>
            <Badge variant="outline" className="text-[10px]">
              {retrieval.status}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-4 text-xs text-text-secondary">
            <div>
              <p className="text-[9px] text-text-muted font-bold">启用</p>
              <p>{retrieval.enabled ? '是' : '否'}</p>
            </div>
            <div>
              <p className="text-[9px] text-text-muted font-bold">条目数</p>
              <p className="font-mono">{Array.isArray(retrieval.items) ? retrieval.items.length : 0}</p>
            </div>
          </div>
          <div className="rounded-lg border border-border-default bg-bg-secondary/80 p-3">
            <p className="text-[9px] text-text-muted font-bold mb-1">检索内容</p>
            <p className="text-sm text-text-primary whitespace-pre-wrap break-words max-h-24 overflow-auto leading-6">
              {retrieval.content?.trim() || '-'}
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">当前话题观点</h4>
        <div className="p-3 bg-blue-500/10 rounded-xl border border-blue-500/20">
           <p className="text-sm font-bold text-blue-400">{currentViewpoint || profile.bio || '暂无观点'}</p>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">社交核心指标</h4>
        <div className="grid grid-cols-2 gap-4">
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">影响力 (Influence)</p>
              <p className="text-xl font-mono text-rose-500">{displayMetric(status.influence)}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">活跃度 (Activity)</p>
              <p className="text-xl font-mono text-emerald-500">{displayPercentage(status.activity)}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">关注 / 粉丝</p>
              <p className="text-sm font-mono text-text-primary">{displayRatio(status.followingCount, status.followerCount)}</p>
           </div>
           <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <p className="text-[9px] text-text-muted font-bold">交互次数</p>
              <p className="text-sm font-mono text-text-primary">{displayCount(status.interactionCount)}</p>
           </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">当前实时动作</h4>
        <div className="p-4 bg-accent/5 border border-accent/20 rounded-xl">
           <p className="text-xs font-bold text-accent mb-1">{lastAction?.type || '-'}</p>
           <p className="text-sm text-text-primary italic">"{lastAction?.content || '-'}"</p>
           <div className="mt-3 pt-3 border-t border-accent/10">
              <p className="text-[10px] text-text-muted">决策原因:</p>
              <p className="text-[11px] text-text-secondary">{lastAction?.reason || '-'}</p>
           </div>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">最近轨迹</h4>
        <div className="space-y-3">
          {recentTimeline.length > 0 ? recentTimeline.slice(0, 4).map((item) => (
            <div key={`${item.timestamp}-${item.type}`} className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <div className="flex items-center justify-between gap-3">
                <Badge variant="outline" className="text-[10px]">{item.type}</Badge>
                <span className="text-[10px] text-text-tertiary">{formatTime(item.timestamp)}</span>
              </div>
              <p className="mt-2 text-sm text-text-primary">{item.content || '-'}</p>
              {item.reason ? <p className="mt-1 text-[11px] text-text-muted">{item.reason}</p> : null}
            </div>
          )) : <p className="text-sm text-text-tertiary">暂无轨迹</p>}
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">最近看到的帖子</h4>
        <div className="space-y-3">
          {seenPosts.length > 0 ? seenPosts.slice(0, 3).map((post) => (
            <div key={post.postId} className="p-3 bg-bg-primary rounded-xl border border-border-default">
              <div className="flex items-center justify-between gap-3 text-[10px] text-text-tertiary">
                <span>{post.author}</span>
                <span>{formatTime(post.timestamp)}</span>
              </div>
              <p className="mt-2 text-sm text-text-primary">{post.content}</p>
              <p className="mt-1 text-[11px] text-text-muted">Likes: {displayMetric(post.numLikes)}</p>
            </div>
          )) : <p className="text-sm text-text-tertiary">暂无可见帖子</p>}
        </div>
      </div>
    </div>
  );
}

function getEmptyRetrieval(): AgentMemorySnapshot['retrieval'] {
  return {
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
  };
}

function formatMemoryLength(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value) ? value : '-';
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

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
