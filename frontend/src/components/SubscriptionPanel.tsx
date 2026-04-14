import { Badge, Button, Card, Progress, Switch } from '@/components/ui';
import { MessageCircle, Play, RefreshCcw, Wifi } from 'lucide-react';

export type DatasetPlatform = 'twitter' | 'reddit' | 'tiktok' | 'instagram' | 'facebook';

interface SubscriptionPanelProps {
  selectedPlatform: DatasetPlatform;
  onPlatformChange: (platform: DatasetPlatform) => void;
  onRefresh?: () => void;
  topicCount?: number;
}

const Twitter = MessageCircle;
const Instagram = MessageCircle;
const Facebook = MessageCircle;

const PLATFORMS: Array<{
  id: DatasetPlatform;
  name: string;
  icon: typeof MessageCircle;
  color: string;
  latency: string;
  hasData: boolean;
}> = [
  {
    id: 'twitter',
    name: 'X / Twitter',
    icon: Twitter,
    color: 'text-white',
    latency: '120ms',
    hasData: true,
  },
  {
    id: 'reddit',
    name: 'Reddit',
    icon: MessageCircle,
    color: 'text-orange-500',
    latency: '45ms',
    hasData: false,
  },
  {
    id: 'tiktok',
    name: 'TikTok',
    icon: Play,
    color: 'text-pink-500',
    latency: '-',
    hasData: false,
  },
  {
    id: 'instagram',
    name: 'Instagram',
    icon: Instagram,
    color: 'text-purple-500',
    latency: '-',
    hasData: false,
  },
  {
    id: 'facebook',
    name: 'Facebook',
    icon: Facebook,
    color: 'text-blue-600',
    latency: '210ms',
    hasData: false,
  },
];

export function SubscriptionPanel({
  selectedPlatform,
  onPlatformChange,
  onRefresh,
  topicCount = 0,
}: SubscriptionPanelProps) {
  return (
    <Card className="p-6 bg-bg-secondary border-accent/20 shadow-2xl shadow-accent/5">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Wifi className="w-5 h-5 text-accent animate-pulse" />
            全网数据实时订阅 (Live-Link)
          </h2>
          <p className="text-xs text-text-tertiary">平台保持原展示形式；当前只有 Twitter 数据可用，且一次只能选一个平台</p>
        </div>
        <Button
          type="button"
          variant="outline"
          className="text-xs gap-2 border-border-default"
          onClick={onRefresh}
          disabled={!onRefresh}
        >
          <RefreshCcw className="w-3 h-3" /> 全局刷新
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {PLATFORMS.map((platform) => {
          const isSelected = platform.id === selectedPlatform;
          const statusText = isSelected
            ? platform.hasData
              ? 'CONNECTED'
              : 'NO DATA'
            : platform.hasData
              ? 'STANDBY'
              : 'NO DATA';
          return (
            <button
              key={platform.id}
              type="button"
              onClick={() => onPlatformChange(platform.id)}
              className={`p-4 rounded-2xl border text-left transition-all ${
                isSelected
                  ? 'bg-accent/5 border-accent/30'
                  : 'bg-bg-primary border-border-default opacity-60 hover:opacity-100'
              }`}
            >
              <div className="flex justify-between items-start mb-3">
                <platform.icon className={`w-6 h-6 ${platform.color}`} />
                <Switch
                  checked={isSelected}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      onPlatformChange(platform.id);
                    }
                  }}
                />
              </div>
              <p className="text-sm font-bold">{platform.name}</p>
              <div className="mt-2 flex items-center justify-between">
                <Badge
                  variant="outline"
                  className={`text-[9px] py-0 ${
                    !platform.hasData ? 'text-text-tertiary border-border-default' : ''
                  }`}
                >
                  {statusText}
                </Badge>
                <span className="text-[9px] font-mono text-text-muted">{platform.latency}</span>
              </div>
              {isSelected && (
                <div className="mt-3 space-y-1">
                  <div className="flex justify-between text-[8px] uppercase font-bold text-text-tertiary">
                    <span>数据库筛选状态</span>
                    <span>{platform.hasData ? `${topicCount} Topics` : '0 Topics'}</span>
                  </div>
                  <Progress value={platform.hasData ? 100 : 0} className="h-1" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </Card>
  );
}
