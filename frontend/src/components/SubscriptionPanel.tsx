import { Card, Badge, Progress, Switch } from '@/components/ui'
import { MessageCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 与 Overview / Profiles 共用的平台字面量（无 Mongo 时仍用于类型） */
export type DatasetPlatform = 'twitter' | 'reddit' | 'tiktok' | 'instagram' | 'facebook'

const Twitter = MessageCircle
const Instagram = MessageCircle
const Facebook = MessageCircle

export interface SubscriptionPlatformCard {
  id: string
  name: string
  status: 'connected' | 'syncing' | 'standby' | 'error'
  progress: number
  checked: boolean
  canToggle: boolean
  datasets: number
  note: string
  colorClass?: string
}

interface SubscriptionPanelProps {
  platforms: SubscriptionPlatformCard[]
  selectedPlatform: string
  /** 只读高亮当前正在编辑详情的平台（可与 checked 一致） */
  onSelectPlatform: (platformId: string) => void
  /**
   * 开关状态变化。单选由父级在 checked=true 时互斥；checked=false 为关闭当前订阅视图。
   */
  onTogglePlatform: (platformId: string, checked: boolean) => void
}

const PLATFORM_ICONS = {
  twitter: Twitter,
  reddit: MessageCircle,
  tiktok: MessageCircle,
  instagram: Instagram,
  facebook: Facebook,
} as const

function statusTone(status: SubscriptionPlatformCard['status']) {
  if (status === 'connected') return 'bg-emerald-500/10 text-emerald-500'
  if (status === 'syncing') return 'bg-blue-500/10 text-blue-400'
  if (status === 'error') return 'bg-rose-500/10 text-rose-500'
  return 'bg-text-muted/10 text-text-muted'
}

function statusLabel(status: SubscriptionPlatformCard['status']) {
  if (status === 'connected') return 'CONNECTED'
  if (status === 'syncing') return 'SYNCING'
  if (status === 'error') return 'ERROR'
  return 'STANDBY'
}

export function SubscriptionPanel({
  platforms,
  selectedPlatform,
  onSelectPlatform,
  onTogglePlatform,
}: SubscriptionPanelProps) {
  return (
    <Card className="bg-bg-secondary border-border-default p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
          </div>
          <div>
            <h2 className="text-lg font-bold">全网数据实时订阅 (Live-Link)</h2>
            <p className="text-xs text-text-tertiary">
              单选一个平台订阅后，按日期和快照选择可用的数据集。
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {platforms.map(platform => {
          const Icon = PLATFORM_ICONS[platform.id as keyof typeof PLATFORM_ICONS] || Twitter
          const isSelected = selectedPlatform === platform.id

          return (
            <div
              key={platform.id}
              onClick={() => {
                if (!platform.canToggle) return
                if (platform.checked) {
                  onSelectPlatform(platform.id)
                } else {
                  onTogglePlatform(platform.id, true)
                }
              }}
              className={cn(
                'p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden group',
                isSelected
                  ? 'bg-accent/5 border-accent/50'
                  : 'bg-bg-primary border-border-default hover:border-accent/30',
                !platform.canToggle && 'opacity-60 cursor-not-allowed'
              )}
            >
              <div className="flex justify-between items-start mb-4">
                <Icon className={cn('w-6 h-6', platform.colorClass || 'text-text-primary')} />
                <div
                  onClick={e => e.stopPropagation()}
                  onKeyDown={e => e.stopPropagation()}
                  className="shrink-0"
                >
                  <Switch
                    checked={platform.checked}
                    disabled={!platform.canToggle}
                    onCheckedChange={next => {
                      if (!platform.canToggle) return
                      onTogglePlatform(platform.id, next)
                    }}
                    aria-label={`${platform.name} 订阅`}
                  />
                </div>
              </div>

              <h3 className="font-bold text-sm mb-3">{platform.name}</h3>

              <div className="flex justify-between items-center mb-2">
                <Badge
                  variant="outline"
                  className={cn('text-[9px] px-2 py-0 border-none', statusTone(platform.status))}
                >
                  {statusLabel(platform.status)}
                </Badge>
                <span className="text-[10px] text-text-tertiary font-mono">
                  {platform.datasets} snapshots
                </span>
              </div>

              <p className="text-[11px] text-text-tertiary min-h-[32px]">{platform.note}</p>

              <div className="mt-3 space-y-1.5">
                <div className="flex justify-between text-[9px] text-text-tertiary">
                  <span>数据集载入状态</span>
                  <span>{platform.checked ? platform.progress : 0}%</span>
                </div>
                <Progress value={platform.checked ? platform.progress : 0} className="h-1" />
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
