import { Badge } from '@/components/ui'
import type { AgentDetailResponse } from '@/lib/agentMonitorTypes'
import { displayMetric, displayPercentage, displayCount } from '@/lib/safeDisplay'

type AgentDeepMonitorProps = {
  detail: AgentDetailResponse | null
  loading?: boolean
  error?: string | null
}

export function AgentDeepMonitor({ detail, loading = false, error = null }: AgentDeepMonitorProps) {
  if (loading) {
    return (
      <StatePanel title="正在加载 Agent 详情" description="请稍候，正在从数据库获取真实数据。" />
    )
  }

  if (error) {
    return <StatePanel title="加载失败" description={error} tone="error" />
  }

  if (!detail) {
    return (
      <StatePanel title="请选择一个 Agent" description="点击左侧图谱节点或表格行查看详细数据。" />
    )
  }

  const { profile, status, lastAction, recentTimeline, seenPosts } = detail

  return (
    <div className="space-y-6">
      {/* 头部：基本信息 */}
      <div className="flex items-center gap-4 border-b border-border-default pb-4">
        <div className="w-12 h-12 bg-accent/20 rounded-full flex items-center justify-center text-xl">
          🤖
        </div>
        <div>
          <h3 className="font-bold text-lg">{profile.name}</h3>
          <p className="text-xs text-text-tertiary">@{profile.user_name || profile.id}</p>
        </div>
      </div>

      {/* 档案信息 */}
      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">
          档案信息
        </h4>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">个人简介</p>
          <p className="text-sm text-text-primary leading-relaxed">{profile.bio || '暂无简介'}</p>
        </div>
        <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
          <p className="text-[9px] text-text-muted font-bold mb-2">兴趣标签</p>
          <div className="flex flex-wrap gap-2">
            {profile.tags?.length ? (
              profile.tags.map((interest, idx) => (
                <Badge key={idx} variant="outline" className="text-[10px] bg-bg-secondary">
                  {interest}
                </Badge>
              ))
            ) : (
              <span className="text-xs text-text-tertiary">无</span>
            )}
          </div>
        </div>
      </div>

      {/* 社交核心指标 */}
      <div className="space-y-4">
        <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">
          社交核心指标
        </h4>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">影响力</p>
            <p className="text-xl font-mono text-accent">{displayMetric(status.influence)}</p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">活跃度</p>
            <p className="text-xl font-mono text-emerald-500">
              {displayPercentage(status.activity)}
            </p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">关注 / 粉丝</p>
            <p className="text-sm font-mono text-text-primary">
              {status.followingCount} / {status.followerCount}
            </p>
          </div>
          <div className="p-3 bg-bg-primary rounded-xl border border-border-default">
            <p className="text-[9px] text-text-muted font-bold">交互次数</p>
            <p className="text-sm font-mono text-text-primary">
              {displayCount(status.interactionCount)}
            </p>
          </div>
        </div>
      </div>

      {/* 最近帖子 */}
      {seenPosts.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">
            最近帖子
          </h4>
          <div className="space-y-3">
            {seenPosts.slice(0, 3).map(post => (
              <div
                key={post.postId}
                className="p-3 bg-bg-primary rounded-xl border border-border-default"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[10px] text-text-tertiary">{post.author}</span>
                  <span className="text-[10px] text-text-tertiary">
                    {formatTime(post.timestamp)}
                  </span>
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
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">
            最新动作
          </h4>
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
          <h4 className="text-[10px] font-bold text-text-tertiary uppercase tracking-widest">
            行为轨迹
          </h4>
          <div className="space-y-3 max-h-80 overflow-auto">
            {recentTimeline.slice(0, 10).map((item, idx) => (
              <div
                key={`${item.timestamp}-${item.type}-${idx}`}
                className="p-3 bg-bg-primary rounded-xl border border-border-default"
              >
                <div className="flex items-center justify-between gap-3">
                  <Badge variant="outline" className="text-[10px]">
                    {item.type}
                  </Badge>
                  <span className="text-[10px] text-text-tertiary">
                    {formatTime(item.timestamp)}
                  </span>
                </div>
                {item.content && <p className="mt-2 text-sm text-text-primary">{item.content}</p>}
                {item.reason && <p className="mt-1 text-[11px] text-text-muted">{item.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatePanel({
  title,
  description,
  tone = 'default',
}: {
  title: string
  description: string
  tone?: 'default' | 'error'
}) {
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
  )
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
