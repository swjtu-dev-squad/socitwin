import {
  Button,
  Badge,
  ScrollArea
} from '@/components/ui';
import { Agent } from '@/lib/types';
import { 
  User, 
  Brain, 
  History, 
  Tag,
  MessageSquare,
  FileText,
  X
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';

interface AgentDetailDrawerProps {
  agent: Agent | null;
  open: boolean;
  onClose: () => void;
}

export default function AgentDetailDrawer({ agent, open, onClose }: AgentDetailDrawerProps) {
  const navigate = useNavigate();
  if (!agent) return null;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed inset-y-0 right-0 w-full max-w-xl bg-bg-secondary border-l border-border-default z-50 shadow-2xl flex flex-col"
          >
            <div className="p-6 border-b border-border-default flex justify-between items-center bg-bg-secondary/50 backdrop-blur-md sticky top-0 z-10">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-accent/20 flex items-center justify-center text-accent border border-accent/30">
                  <User className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-bold">{agent.name}</h2>
                  <p className="text-[10px] text-text-tertiary font-mono uppercase tracking-widest">{agent.id}</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} className="rounded-full">
                <X className="w-5 h-5" />
              </Button>
            </div>

            <ScrollArea className="flex-1 p-8 space-y-10">
              <section className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-text-tertiary">
                  <Tag className="w-3.5 h-3.5" /> 基础画像
                </div>
                <div className="bg-bg-primary/50 border border-border-default p-6 rounded-2xl space-y-4">
                  <p className="text-sm text-text-secondary leading-relaxed italic">"{agent.bio}"</p>
                  <div className="flex flex-wrap gap-2">
                    {agent.interests.map(interest => (
                      <Badge key={interest} variant="secondary" className="bg-bg-tertiary border-border-default text-[9px]">
                        {interest}
                      </Badge>
                    ))}
                  </div>
                </div>
              </section>

              <section className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-text-tertiary">
                  <Brain className="w-3.5 h-3.5" /> 认知状态
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-2xl bg-bg-primary/50 border border-border-default">
                    <p className="text-[10px] font-bold text-text-tertiary uppercase mb-1">极化程度</p>
                    <p className="text-2xl font-mono font-bold text-rose-500">{(agent.polarization || 0).toFixed(4)}</p>
                  </div>
                  <div className="p-4 rounded-2xl bg-bg-primary/50 border border-border-default">
                    <p className="text-[10px] font-bold text-text-tertiary uppercase mb-1">活跃状态</p>
                    <Badge variant={agent.status === 'active' ? 'default' : 'secondary'} className="mt-1">
                      {agent.status}
                    </Badge>
                  </div>
                </div>
              </section>

              <section className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-text-tertiary">
                  <History className="w-3.5 h-3.5" /> 最近轨迹
                </div>
                <div className="space-y-4 relative pl-4 border-l border-border-default">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="relative">
                      <div className="absolute -left-[21px] top-1.5 w-2.5 h-2.5 rounded-full bg-bg-secondary border-2 border-accent" />
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold text-accent uppercase">Create Post</span>
                          <span className="text-[9px] text-text-muted font-mono">2m ago</span>
                        </div>
                        <p className="text-xs text-text-secondary">发表了关于“AI伦理”的看法，引起了广泛讨论。</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </ScrollArea>

            <div className="p-6 border-t border-border-default bg-bg-secondary/50 backdrop-blur-md grid grid-cols-2 gap-4">
              <Button variant="outline" className="rounded-xl h-12 gap-2" onClick={() => navigate(`/logs?agent=${agent.id}`)}>
                <FileText className="w-4 h-4" />
                查看日志
              </Button>
              <Button className="rounded-xl h-12 gap-2">
                <MessageSquare className="w-4 h-4" />
                注入指令
              </Button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
