import { 
  Drawer, 
  DrawerContent, 
  DrawerHeader, 
  DrawerTitle, 
  DrawerDescription, 
  DrawerFooter, 
  DrawerClose, 
  Button, 
  Badge 
} from '@/components/ui';
import { Agent } from '@/lib/types';
import { 
  User, 
  Brain, 
  History, 
  Tag,
  MessageSquare,
  FileText,
  ExternalLink
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface AgentDetailDrawerProps {
  agent: Agent | null;
  open: boolean;
  onClose: () => void;
}

export default function AgentDetailDrawer({ agent, open, onClose }: AgentDetailDrawerProps) {
  const navigate = useNavigate();
  if (!agent) return null;

  return (
    <Drawer open={open} onClose={onClose}>
      <DrawerContent className="bg-zinc-900 border-zinc-800 text-zinc-100 max-w-2xl mx-auto">
        <div className="mx-auto w-12 h-1.5 bg-zinc-800 rounded-full mt-4" />
        
        <DrawerHeader className="px-8 pt-8">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-16 h-16 bg-emerald-500/10 border border-emerald-500/50 rounded-2xl flex items-center justify-center text-3xl">
                🤖
              </div>
              <div>
                <DrawerTitle className="text-2xl font-bold flex items-center gap-3">
                  {agent.name}
                  <Badge variant={agent.status === 'active' ? 'default' : 'secondary'} className={agent.status === 'active' ? 'bg-emerald-500' : ''}>
                    {agent.status === 'active' ? '活跃' : '空闲'}
                  </Badge>
                </DrawerTitle>
                <DrawerDescription className="text-zinc-500 font-mono text-xs mt-1">
                  ID: {agent.id}
                </DrawerDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 text-[10px] border-zinc-800 rounded-lg gap-1.5"
                onClick={() => {
                  navigate(`/logs?agent=${agent.id}`);
                  onClose();
                }}
              >
                <FileText className="w-3.5 h-3.5" />
                日志
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 text-[10px] border-zinc-800 rounded-lg gap-1.5"
                onClick={() => {
                  navigate(`/groupchat`);
                  onClose();
                }}
              >
                <MessageSquare className="w-3.5 h-3.5" />
                群聊
              </Button>
            </div>
          </div>
        </DrawerHeader>

        <div className="px-8 py-4 space-y-8 overflow-y-auto max-h-[60vh]">
          {/* Profile Section */}
          <section className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-2">
              <User className="w-4 h-4" /> 个人档案
            </h3>
            <div className="bg-zinc-950/50 border border-zinc-800 rounded-2xl p-6">
              <p className="text-zinc-300 leading-relaxed italic">"{agent.bio}"</p>
              <div className="mt-6 flex flex-wrap gap-2">
                {agent.interests.map(interest => (
                  <Badge key={interest} variant="outline" className="bg-zinc-900 border-zinc-800 text-zinc-400">
                    <Tag className="w-3 h-3 mr-1" /> {interest}
                  </Badge>
                ))}
              </div>
            </div>
          </section>

          {/* Memory Section */}
          <section className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-2">
              <Brain className="w-4 h-4" /> 记忆检索 (Memory)
            </h3>
            <div className="grid grid-cols-1 gap-3">
              {[
                { content: '观察到关于“AI伦理”的讨论，产生了浓厚兴趣', time: '2分钟前', type: 'Observation' },
                { content: '记录了与 Agent_12 的互动，对方观点较为激进', time: '5分钟前', type: 'Interaction' },
                { content: '在 Reddit 平台浏览了 5 条热门帖子', time: '12分钟前', type: 'Browsing' },
              ].map((memory, i) => (
                <div key={i} className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/50 group hover:border-emerald-500/30 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-[9px] font-bold uppercase tracking-widest text-emerald-500/70 bg-emerald-500/5 px-2 py-0.5 rounded border border-emerald-500/10">
                      {memory.type}
                    </span>
                    <span className="text-[9px] text-zinc-600 font-mono">{memory.time}</span>
                  </div>
                  <p className="text-xs text-zinc-400 leading-relaxed">{memory.content}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Action History */}
          <section className="space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-500 flex items-center gap-2">
              <History className="w-4 h-4" /> 动作历史
            </h3>
            <div className="space-y-4">
              <div className="relative pl-6 border-l border-zinc-800 space-y-6">
                <div className="relative">
                  <div className="absolute -left-[25px] top-1 w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]"></div>
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-bold text-emerald-400">{agent.lastAction?.type}</p>
                      <p className="text-xs text-zinc-300 mt-1">“{agent.lastAction?.content}”</p>
                      <p className="text-[10px] text-zinc-500 mt-2 italic">Reason: {agent.lastAction?.reason}</p>
                    </div>
                    <span className="text-[10px] text-zinc-600 font-mono">09:12:45</span>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <DrawerFooter className="px-8 pb-8 pt-4 border-t border-zinc-800">
          <div className="flex gap-4">
            <Button className="flex-1 bg-emerald-600 hover:bg-emerald-700 rounded-xl h-12">
              <MessageSquare className="w-4 h-4 mr-2" /> 注入动作
            </Button>
            <DrawerClose asChild>
              <Button variant="outline" className="flex-1 border-zinc-800 hover:bg-zinc-800 rounded-xl h-12" onClick={onClose}>
                关闭
              </Button>
            </DrawerClose>
          </div>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
