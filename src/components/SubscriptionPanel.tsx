import { useState } from 'react';
import { Card, Button, Badge, Switch, Progress } from '@/components/ui';
import { Twitter, MessageCircle, Play, Instagram, Facebook, RefreshCcw, Wifi } from 'lucide-react';

const PLATFORMS = [
  { id: 'x', name: 'X / Twitter', icon: Twitter, color: 'text-white', status: 'connected', latency: '120ms' },
  { id: 'reddit', name: 'Reddit', icon: MessageCircle, color: 'text-orange-500', status: 'connected', latency: '45ms' },
  { id: 'tiktok', name: 'TikTok', icon: Play, color: 'text-pink-500', status: 'standby', latency: '-' },
  { id: 'instagram', name: 'Instagram', icon: Instagram, color: 'text-purple-500', status: 'error', latency: '-' },
  { id: 'facebook', name: 'Facebook', icon: Facebook, color: 'text-blue-600', status: 'connected', latency: '210ms' },
];

export function SubscriptionPanel() {
  const [platforms, setPlatforms] = useState(PLATFORMS);

  const togglePlatform = (id: string) => {
    setPlatforms(prev => prev.map(p => 
      p.id === id ? { ...p, status: p.status === 'connected' ? 'standby' : 'connected' } : p
    ));
  };

  return (
    <Card className="p-6 bg-bg-secondary border-accent/20 shadow-2xl shadow-accent/5">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Wifi className="w-5 h-5 text-accent animate-pulse" />
            全网数据实时订阅 (Live-Link)
          </h2>
          <p className="text-xs text-text-tertiary">订阅真实平台数据流，自动合成仿真实体三元组</p>
        </div>
        <Button variant="outline" className="text-xs gap-2 border-border-default">
          <RefreshCcw className="w-3 h-3" /> 全局刷新
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {platforms.map((p) => (
          <div key={p.id} className={`p-4 rounded-2xl border transition-all ${p.status === 'connected' ? 'bg-accent/5 border-accent/30' : 'bg-bg-primary border-border-default opacity-60'}`}>
            <div className="flex justify-between items-start mb-3">
              <p.icon className={`w-6 h-6 ${p.color}`} />
              <Switch 
                checked={p.status === 'connected'} 
                onCheckedChange={() => togglePlatform(p.id)}
              />
            </div>
            <p className="text-sm font-bold">{p.name}</p>
            <div className="mt-2 flex items-center justify-between">
              <Badge variant="outline" className={`text-[9px] py-0 ${p.status === 'error' ? 'text-rose-500 border-rose-500/20' : ''}`}>
                {p.status.toUpperCase()}
              </Badge>
              <span className="text-[9px] font-mono text-text-muted">{p.latency}</span>
            </div>
            {p.status === 'connected' && (
              <div className="mt-3 space-y-1">
                <div className="flex justify-between text-[8px] uppercase font-bold text-text-tertiary">
                  <span>三元组合成进度</span>
                  <span>88%</span>
                </div>
                <Progress value={88} className="h-1" />
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
