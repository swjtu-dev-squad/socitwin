import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  SlidersHorizontal,
  UserRound,
  Users,
  MessageSquare,
  BarChart3,
  Settings as SettingsIcon,
  MessageCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';
import OasisIcon from './OasisIcon';

const navItems = [
  { name: '概览', icon: Home, href: '/overview' },
  { name: '控制中心', icon: SlidersHorizontal, href: '/control' },
  { name: '用户画像生成', icon: UserRound, href: '/profiles' },
  { name: '智能体监控', icon: Users, href: '/agents' },
  { name: '通信日志', icon: MessageSquare, href: '/logs' },
  { name: '群聊监控', icon: MessageCircle, href: '/groupchat' },
  { name: '分析仪表板', icon: BarChart3, href: '/analytics' },
  { name: '设置', icon: SettingsIcon, href: '/settings' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border-default bg-bg-secondary/50 flex flex-col glass-effect">
        <div className="p-6 flex items-center gap-3">
          <OasisIcon size={40} />
          <div>
            <h1 className="font-bold text-xl tracking-tight">OASIS</h1>
            <p className="text-[10px] text-accent font-mono uppercase tracking-widest gradient-text">Simulation OS</p>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-gradient-to-r from-accent to-accent-light text-white shadow-lg glow-effect"
                    : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                )}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border-default">
          <div className="bg-bg-tertiary/50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-text-tertiary uppercase font-bold tracking-wider">System Status</span>
              <span className="w-2 h-2 bg-accent rounded-full animate-pulse shadow-[0_0_8px_rgba(215,38,56,0.8)]"></span>
            </div>
            <p className="text-xs text-text-secondary">v1.0.0 Stable</p>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto relative">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(215,38,56,0.08),transparent_50%)] pointer-events-none"></div>
        {children}
      </main>
    </div>
  );
}
