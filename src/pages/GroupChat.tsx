import { useState, useEffect, useRef } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Badge, Button, Input, ScrollArea, Switch } from '@/components/ui';
import { Users, MessageCircle, Send, Plus, Search, Hash, RefreshCw, Twitter, MessageSquare, Video, Instagram, Facebook } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from '@/lib/utils';

// Mock data for platforms
const PLATFORMS = [
  { id: 'twitter', name: 'X / Twitter', icon: Twitter, status: 'CONNECTED', latency: '120ms', progress: 88, defaultOn: true, color: 'text-blue-400' },
  { id: 'reddit', name: 'Reddit', icon: MessageSquare, status: 'CONNECTED', latency: '45ms', progress: 88, defaultOn: true, color: 'text-orange-500' },
  { id: 'tiktok', name: 'TikTok', icon: Video, status: 'STANDBY', latency: '-', progress: 0, defaultOn: false, color: 'text-pink-500' },
  { id: 'instagram', name: 'Instagram', icon: Instagram, status: 'ERROR', latency: '-', progress: 0, defaultOn: false, color: 'text-purple-500' },
  { id: 'facebook', name: 'Facebook', icon: Facebook, status: 'CONNECTED', latency: '210ms', progress: 88, defaultOn: true, color: 'text-blue-600' },
];

// Generate mock topics for a platform
const generateTopics = (platformId: string) => {
  return Array.from({ length: 20 }, (_, i) => ({
    id: `${platformId}_topic_${i}`,
    name: `${platformId.toUpperCase()} Topic ${i + 1}`,
    members: Math.floor(Math.random() * 1000) + 10,
    polarization: Math.random(),
    lastMsg: `Latest discussion on ${platformId} topic ${i + 1}...`
  })).sort((a, b) => b.members - a.members);
};

export default function GroupChat() {
  const { groupMessages } = useSimulationStore();
  const [inputMessage, setInputMessage] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const [platformStates, setPlatformStates] = useState<Record<string, boolean>>(
    Object.fromEntries(PLATFORMS.map(p => [p.id, p.defaultOn]))
  );
  const [selectedPlatform, setSelectedPlatform] = useState<string>('twitter');
  
  const [groups, setGroups] = useState(generateTopics('twitter'));
  const [activeGroup, setActiveGroup] = useState(groups[0]);

  useEffect(() => {
    const newGroups = generateTopics(selectedPlatform);
    setGroups(newGroups);
    setActiveGroup(newGroups[0]);
  }, [selectedPlatform]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [groupMessages]);

  const togglePlatform = (id: string, val: boolean) => {
    setPlatformStates(prev => ({ ...prev, [id]: val }));
  };

  return (
    <div className="px-6 lg:px-12 py-10 space-y-8 h-full flex flex-col overflow-hidden">
      <header className="flex justify-between items-center shrink-0">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <MessageCircle className="w-10 h-10 text-accent" />
            热门话题监控
          </h1>
          <p className="text-text-tertiary mt-1">实时观测群体讨论、意见形成与共谋行为</p>
        </div>
      </header>

      {/* Live-Link Section */}
      <Card className="bg-bg-secondary border-border-default p-6 shrink-0">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              </div>
            </div>
            <div>
              <h2 className="text-lg font-bold">全网数据实时订阅 (Live-Link)</h2>
              <p className="text-xs text-text-tertiary">订阅真实平台数据流，自动合成仿真实体三元组</p>
            </div>
          </div>
          <Button variant="outline" size="sm" className="gap-2 border-border-default hover:bg-bg-tertiary text-xs">
            <RefreshCw className="w-3.5 h-3.5" /> 全局刷新
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {PLATFORMS.map(platform => {
            const isOn = platformStates[platform.id];
            const isSelected = selectedPlatform === platform.id;
            
            return (
              <div 
                key={platform.id}
                onClick={() => setSelectedPlatform(platform.id)}
                className={cn(
                  "p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden group",
                  isSelected ? "bg-accent/5 border-accent/50" : "bg-bg-primary border-border-default hover:border-accent/30"
                )}
              >
                <div className="flex justify-between items-start mb-4">
                  <platform.icon className={cn("w-6 h-6", platform.color)} />
                  <div onClick={e => e.stopPropagation()}>
                    <Switch 
                      checked={isOn} 
                      onCheckedChange={(val) => togglePlatform(platform.id, val)}
                      className="data-[state=checked]:bg-emerald-500"
                    />
                  </div>
                </div>
                
                <h3 className="font-bold text-sm mb-3">{platform.name}</h3>
                
                <div className="flex justify-between items-center mb-4">
                  <Badge variant="outline" className={cn(
                    "text-[9px] px-2 py-0 border-none",
                    platform.status === 'CONNECTED' ? "bg-emerald-500/10 text-emerald-500" :
                    platform.status === 'ERROR' ? "bg-rose-500/10 text-rose-500" :
                    "bg-text-muted/10 text-text-muted"
                  )}>
                    {platform.status}
                  </Badge>
                  <span className="text-[10px] text-text-tertiary font-mono">{platform.latency}</span>
                </div>

                <div className="space-y-1.5">
                  <div className="flex justify-between text-[9px] text-text-tertiary">
                    <span>三元组合成进度</span>
                    <span>{isOn ? platform.progress : 0}%</span>
                  </div>
                  <div className="h-1 w-full bg-bg-tertiary rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-emerald-500 transition-all duration-500" 
                      style={{ width: `${isOn ? platform.progress : 0}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Group Sidebar */}
        <Card className="col-span-12 lg:col-span-4 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border-default flex justify-between items-center bg-bg-secondary/50">
            <h2 className="text-xs font-bold uppercase tracking-widest text-text-tertiary flex items-center gap-2">
              <Hash className="w-3.5 h-3.5" /> {PLATFORMS.find(p => p.id === selectedPlatform)?.name} 热门话题
            </h2>
            <Badge variant="outline" className="h-5 px-2 border-accent/20 text-accent bg-accent/5 text-[10px]">
              Top 20
            </Badge>
          </div>
          
          <div className="p-4 border-b border-border-default shrink-0">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
              <Input placeholder="搜索话题..." className="pl-9 h-9 text-xs rounded-xl bg-bg-primary border-border-default" />
            </div>
          </div>

          <ScrollArea className="flex-1 px-3 pb-4 pt-2">
            <div className="space-y-2">
              {groups.map((group, idx) => (
                <div
                  key={group.id}
                  onClick={() => setActiveGroup(group)}
                  className={cn(
                    "p-4 rounded-xl cursor-pointer transition-all duration-200 border group flex gap-3",
                    activeGroup?.id === group.id 
                      ? "bg-accent/10 border-accent/30" 
                      : "bg-bg-primary border-transparent hover:border-border-default"
                  )}
                >
                  <div className="w-6 h-6 rounded-full bg-bg-tertiary flex items-center justify-center text-[10px] font-bold text-text-muted shrink-0">
                    {idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-1">
                      <h4 className={cn("font-bold text-sm truncate pr-2", activeGroup?.id === group.id ? "text-accent" : "text-text-primary")}>
                        {group.name}
                      </h4>
                      <span className={cn("text-[10px] font-mono font-bold shrink-0", group.polarization > 0.8 ? "text-rose-500" : "text-text-tertiary")}>
                        {(group.polarization * 100).toFixed(0)}% 极化
                      </span>
                    </div>
                    <div className="flex justify-between text-[10px] text-text-muted font-bold uppercase tracking-tighter">
                      <span>{group.members} 参与者</span>
                    </div>
                    <p className="text-xs text-text-tertiary mt-2 line-clamp-1 italic">“{group.lastMsg}”</p>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </Card>

        {/* Chat Window */}
        <Card className="col-span-12 lg:col-span-8 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-bg-tertiary rounded-xl flex items-center justify-center text-accent border border-border-default">
                <Hash className="w-5 h-5" />
              </div>
              <div>
                <h2 className="font-bold text-lg">{activeGroup?.name || '选择话题'}</h2>
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></div>
                  <p className="text-[10px] text-text-tertiary font-bold uppercase tracking-widest">{activeGroup?.members || 0} 参与者正在讨论</p>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="h-8 rounded-lg border-border-default text-[10px] font-bold">导出记录</Button>
            </div>
          </div>

          <ScrollArea className="flex-1 p-6 space-y-6" ref={scrollRef}>
            <AnimatePresence initial={false}>
              {groupMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-text-muted py-20 opacity-20">
                  <MessageCircle className="w-16 h-16 mb-4" />
                  <p className="text-xs uppercase tracking-widest font-bold">Waiting for agent interactions...</p>
                </div>
              ) : (
                groupMessages.map((msg, i) => (
                  <motion.div 
                    key={msg.id || i}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex gap-4 group"
                  >
                    <div className="w-10 h-10 rounded-xl bg-bg-tertiary flex items-center justify-center text-xs font-bold text-accent border border-border-default shrink-0">
                      {msg.agentName.charAt(0)}
                    </div>
                    <div className="flex-1 space-y-1.5">
                      <div className="flex items-baseline gap-2">
                        <span className="text-xs font-bold text-text-primary">{msg.agentName}</span>
                        <span className="text-[9px] text-text-muted font-mono">{msg.timestamp}</span>
                      </div>
                      <div className="bg-bg-primary/50 border border-border-default p-4 rounded-2xl rounded-tl-none group-hover:border-border-strong transition-colors">
                        <p className="text-sm text-text-secondary leading-relaxed">{msg.content}</p>
                        {msg.reason && (
                          <div className="mt-3 pt-3 border-t border-border-default/50 text-[10px] text-text-tertiary italic">
                            <span className="font-bold uppercase tracking-tighter text-text-muted mr-2">Logic:</span>
                            {msg.reason}
                          </div>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
          </ScrollArea>

          <div className="p-4 border-t border-border-default bg-bg-primary/30 flex gap-3 shrink-0">
            <Input 
              placeholder="注入人工指令 (ManualAction)..." 
              className="bg-bg-secondary border-border-default rounded-2xl h-12 text-sm"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setInputMessage('')}
            />
            <Button 
              className="w-12 h-12 p-0 rounded-2xl bg-accent hover:bg-accent-hover shrink-0"
              onClick={() => setInputMessage('')}
            >
              <Send className="w-5 h-5" />
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
