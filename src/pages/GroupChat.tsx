import { useState, useEffect } from 'react';
import { useSimulationStore } from '@/lib/store';
import { Card, Badge, Button, Input, ScrollArea } from '@/components/ui';
import { Users, MessageCircle, TrendingUp, Send, Plus } from 'lucide-react';
import { simulationApi } from '@/lib/api';

interface GroupChat {
  id: string;
  name: string;
  memberCount: number;
  polarization: number;
  lastMessage: string;
  lastTime: string;
}

export default function GroupChat() {
  const { groupMessages } = useSimulationStore();
  const [groups] = useState<GroupChat[]>([
    { id: 'g1', name: 'FlatEarth-Discuss', memberCount: 23, polarization: 0.94, lastMessage: '地球真的是平的！', lastTime: '09:14:32' },
    { id: 'g2', name: 'AI-Ethics', memberCount: 41, polarization: 0.67, lastMessage: '这个模型太危险了', lastTime: '09:14:28' },
    { id: 'g3', name: 'Politics-2026', memberCount: 18, polarization: 0.82, lastMessage: '投票结果出来了', lastTime: '09:14:25' },
  ]);

  const [activeGroup, setActiveGroup] = useState<GroupChat>(groups[0]);
  const [inputMessage, setInputMessage] = useState('');

  const handleSendMessage = async () => {
    if (!inputMessage.trim()) return;
    try {
      await simulationApi.sendGroupMessage(inputMessage);
      setInputMessage('');
    } catch (e) {
      console.error('Failed to send message', e);
    }
  };

  return (
    <div className="px-6 lg:px-12 xl:px-16 py-12 h-full flex flex-col">
      <div className="max-w-7xl mx-auto space-y-8 flex-1 min-h-0">
      <header className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight flex items-center gap-3">
            <MessageCircle className="w-10 h-10 text-accent" />
            群聊监控
          </h1>
          <p className="text-text-tertiary mt-1">实时观测群体讨论、意见形成与共谋行为</p>
        </div>
        <div className="text-accent font-mono text-sm bg-accent/5 px-4 py-2 rounded-full border border-accent/20">
          活跃群聊: {groups.length} 个 | 总消息: 18,942 条
        </div>
      </header>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Group List */}
        <Card className="col-span-4 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border-default flex justify-between items-center bg-bg-secondary/50">
            <h2 className="text-sm font-bold uppercase tracking-widest text-text-tertiary flex items-center gap-2">
              <Users className="w-4 h-4" /> 群聊列表
            </h2>
            <Button variant="outline" className="h-8 w-8 p-0 rounded-lg border-border-default">
              <Plus className="w-4 h-4" />
            </Button>
          </div>
          <ScrollArea className="flex-1 p-3 space-y-2">
            {groups.map(group => (
              <div
                key={group.id}
                onClick={() => setActiveGroup(group)}
                className={cn(
                  "p-4 rounded-2xl cursor-pointer transition-all duration-200 border",
                  activeGroup.id === group.id 
                    ? "bg-accent-subtle border-accent/50" 
                    : "bg-bg-primary border-transparent hover:bg-bg-tertiary"
                )}
              >
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-bold text-text-primary">{group.name}</h4>
                  <Badge variant={group.polarization > 0.8 ? 'destructive' : 'secondary'}>
                    {group.polarization.toFixed(2)}
                  </Badge>
                </div>
                <div className="flex justify-between text-[10px] text-text-tertiary font-mono">
                  <span>{group.memberCount} 成员</span>
                  <span>{group.lastTime}</span>
                </div>
                <p className="text-xs text-text-secondary mt-2 line-clamp-1 italic">“{group.lastMessage}”</p>
              </div>
            ))}
          </ScrollArea>
        </Card>

        {/* Chat Window */}
        <Card className="col-span-5 bg-bg-secondary border-border-default flex flex-col overflow-hidden">
          <div className="p-4 border-b border-border-default bg-bg-secondary/50 flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-accent/20 rounded-lg flex items-center justify-center text-accent">💬</div>
              <div>
                <h2 className="text-sm font-bold">{activeGroup.name}</h2>
                <p className="text-[10px] text-accent font-mono uppercase tracking-widest">Live Stream</p>
              </div>
            </div>
            <Badge variant="outline" className="border-border-default text-text-tertiary">
              {activeGroup.memberCount} 人在线
            </Badge>
          </div>

          <ScrollArea className="flex-1 p-6 space-y-6 font-mono text-sm">
            {groupMessages.map((msg, i) => (
              <div key={i} className="flex gap-4 group animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="font-bold text-accent w-24 shrink-0 text-right pt-1">{msg.agentName}</div>
                <div className="flex-1 space-y-2">
                  <div className="bg-bg-primary/50 border border-border-default p-4 rounded-2xl rounded-tl-none group-hover:border-border-strong transition-colors">
                    <div className="text-text-primary leading-relaxed">{msg.content}</div>
                    {msg.reason && (
                      <div className="mt-3 pt-3 border-t border-border-default/50 text-[10px] text-text-tertiary italic flex items-center gap-2">
                        <span className="text-text-muted font-bold uppercase tracking-tighter">Reason:</span>
                        {msg.reason}
                      </div>
                    )}
                  </div>
                </div>
                <div className="text-[10px] text-text-muted shrink-0 pt-1">{msg.timestamp}</div>
              </div>
            ))}
            {/* Thinking Animation */}
            {groupMessages.length > 0 && (
              <div className="flex gap-4 animate-pulse">
                <div className="font-bold text-blue-400 w-24 shrink-0 text-right pt-1">Agent_Thinking</div>
                <div className="flex-1">
                  <div className="bg-blue-500/5 border border-blue-500/20 p-3 rounded-2xl rounded-tl-none w-20 flex justify-center gap-1">
                    <div className="w-1 h-1 bg-blue-400 rounded-full animate-bounce"></div>
                    <div className="w-1 h-1 bg-blue-400 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                    <div className="w-1 h-1 bg-blue-400 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                  </div>
                </div>
              </div>
            )}
            {groupMessages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-text-muted py-20">
                <MessageCircle className="w-12 h-12 mb-4 opacity-10" />
                <p className="text-xs uppercase tracking-widest font-bold">Waiting for messages...</p>
              </div>
            )}
          </ScrollArea>

          <div className="p-4 border-t border-border-default bg-bg-primary/50 flex gap-3">
            <Input 
              placeholder="注入群消息 (ManualAction)..." 
              className="bg-bg-secondary border-border-default rounded-xl h-12"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            />
            <Button 
              onClick={handleSendMessage}
              className="w-12 h-12 p-0 rounded-xl bg-accent hover:bg-accent-hover"
            >
              <Send className="w-5 h-5" />
            </Button>
          </div>
        </Card>

        {/* Group Stats */}
        <div className="col-span-3 space-y-6">
          <Card className="bg-bg-secondary border-border-default p-6 space-y-8">
            <h3 className="text-xs font-bold uppercase tracking-widest text-text-tertiary flex items-center gap-2">
              <TrendingUp className="w-4 h-4" /> 群聊统计
            </h3>
            <div className="space-y-6">
              <div>
                <p className="text-[10px] text-text-tertiary uppercase font-bold tracking-wider">极化指数</p>
                <p className="text-5xl font-bold text-rose-400 mt-2 font-mono">{activeGroup.polarization}</p>
              </div>
              <div>
                <p className="text-[10px] text-text-tertiary uppercase font-bold tracking-wider">消息速度</p>
                <p className="text-3xl font-bold mt-2 font-mono">47 <span className="text-xs font-normal text-text-tertiary">条/分</span></p>
              </div>
            </div>
          </Card>

          <div className="space-y-3">
            <Button className="w-full h-14 rounded-2xl bg-accent hover:bg-accent-hover text-base font-bold shadow-lg shadow-accent-glow">
              创建新群聊
            </Button>
            <Button variant="outline" className="w-full h-14 rounded-2xl border-border-default hover:bg-bg-tertiary text-base font-bold">
              导出群聊记录
            </Button>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}

function cn(...inputs: any[]) {
  return inputs.filter(Boolean).join(' ');
}
