import { Card, Button, Badge, Switch, Progress } from '@/components/ui';
import { Twitter, MessageCircle, Play, Instagram, Facebook, RefreshCcw, Wifi } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SubscriptionPlatformCard {
  id: string;
  name: string;
  status: 'connected' | 'syncing' | 'standby' | 'error';
  latency: string;
  progress: number;
  checked: boolean;
  canToggle: boolean;
  datasets: number;
  note: string;
  lastDatasetId?: string;
  colorClass?: string;
}

interface SubscriptionPanelProps {
  platforms: SubscriptionPlatformCard[];
  selectedPlatform: string;
  refreshing?: boolean;
  onSelectPlatform: (platformId: string) => void;
  onTogglePlatform: (platformId: string, checked: boolean) => void;
  onRefresh: () => void;
}

const PLATFORM_ICONS = {
  twitter: Twitter,
  reddit: MessageCircle,
  tiktok: Play,
  instagram: Instagram,
  facebook: Facebook,
} as const;

function statusTone(status: SubscriptionPlatformCard['status']) {
  if (status === 'connected') return 'bg-emerald-500/10 text-emerald-500';
  if (status === 'syncing') return 'bg-blue-500/10 text-blue-400';
  if (status === 'error') return 'bg-rose-500/10 text-rose-500';
  return 'bg-text-muted/10 text-text-muted';
}

function statusLabel(status: SubscriptionPlatformCard['status']) {
  if (status === 'connected') return 'CONNECTED';
  if (status === 'syncing') return 'SYNCING';
  if (status === 'error') return 'ERROR';
  return 'STANDBY';
}

export function SubscriptionPanel({
  platforms,
  selectedPlatform,
  refreshing = false,
  onSelectPlatform,
  onTogglePlatform,
  onRefresh,
}: SubscriptionPanelProps) {
  return (
    <Card className="bg-bg-secondary border-border-default p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
          </div>
          <div>
            <h2 className="text-lg font-bold">全网数据实时订阅 (Live-Link)</h2>
            <p className="text-xs text-text-tertiary">订阅平台后，加载该平台当前可用的数据集。</p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="gap-2 border-border-default hover:bg-bg-tertiary text-xs"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCcw className={cn('w-3.5 h-3.5', refreshing && 'animate-spin')} />
          全局刷新
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {platforms.map((platform) => {
          const Icon = PLATFORM_ICONS[platform.id as keyof typeof PLATFORM_ICONS] || Twitter;
          const isSelected = selectedPlatform === platform.id;

          return (
            <div
              key={platform.id}
              onClick={() => onSelectPlatform(platform.id)}
              className={cn(
                'p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden group',
                isSelected ? 'bg-accent/5 border-accent/50' : 'bg-bg-primary border-border-default hover:border-accent/30',
              )}
            >
              <div className="flex justify-between items-start mb-4">
                <Icon className={cn('w-6 h-6', platform.colorClass || 'text-text-primary')} />
                <div onClick={(event) => event.stopPropagation()}>
                  <Switch
                    checked={platform.checked}
                    onCheckedChange={(checked) => {
                      if (!platform.canToggle) return;
                      onTogglePlatform(platform.id, checked);
                    }}
                    className={!platform.canToggle ? 'opacity-50 cursor-not-allowed' : undefined}
                  />
                </div>
              </div>

              <h3 className="font-bold text-sm mb-3">{platform.name}</h3>

              <div className="flex justify-between items-center mb-2">
                <Badge variant="outline" className={cn('text-[9px] px-2 py-0 border-none', statusTone(platform.status))}>
                  {statusLabel(platform.status)}
                </Badge>
                <span className="text-[10px] text-text-tertiary font-mono">{platform.latency}</span>
              </div>

              <div className="flex justify-between items-center text-[10px] text-text-tertiary mb-3">
                <span>数据集</span>
                <span className="font-mono text-text-primary">{platform.datasets}</span>
              </div>

              <p className="text-[11px] text-text-tertiary min-h-[32px]">{platform.note}</p>

              <div className="mt-3 space-y-1.5">
                <div className="flex justify-between text-[9px] text-text-tertiary">
                  <span>数据集载入状态</span>
                  <span>{platform.checked ? platform.progress : 0}%</span>
                </div>
                <Progress value={platform.checked ? platform.progress : 0} className="h-1" />
              </div>

              {platform.lastDatasetId ? (
                <div className="mt-3 rounded-lg bg-bg-secondary/70 border border-border-default px-2 py-2">
                  <p className="text-[9px] uppercase tracking-widest text-text-muted">最新 Dataset</p>
                  <p className="text-[10px] font-mono text-text-primary break-all">{platform.lastDatasetId}</p>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
