import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  UserRound,
  Users,
  MessageSquare,
  BarChart3,
  Settings as SettingsIcon,
  MessageCircle,
  Eye,
  FlaskConical
} from 'lucide-react';
import { cn } from '@/lib/utils';
import OasisIcon from './OasisIcon';

const navItems = [
  { name: '概览', icon: Eye, href: '/overview' },
  { name: '用户画像生成', icon: UserRound, href: '/profiles' },
  { name: '智能体监控', icon: Users, href: '/agents' },
  { name: '通信日志', icon: MessageSquare, href: '/logs' },
  { name: '群聊监控', icon: MessageCircle, href: '/groupchat' },
  { name: '分析仪表板', icon: BarChart3, href: '/analytics' },
  { name: '实验控制台', icon: FlaskConical, href: '/experiments' },
  { name: '设置', icon: SettingsIcon, href: '/settings' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-bg-secondary/50 flex flex-col glass-effect">
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
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto relative">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(215,38,56,0.08),transparent_50%)] pointer-events-none"></div>
        {children}
      </main>
    </div>
  );
}
