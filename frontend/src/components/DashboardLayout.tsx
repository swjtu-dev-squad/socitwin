import { Link, useLocation } from 'react-router-dom'
import {
  UserRound,
  Users,
  MessageSquare,
  Settings as SettingsIcon,
  MessageCircle,
  Eye,
  FlaskConical,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { motion } from 'motion/react'
import { Logo } from './Logo'

const navItems = [
  { name: '态势推演', icon: Eye, href: '/overview' },
  { name: '用户画像', icon: UserRound, href: '/profiles' },
  { name: '社交网络监控', icon: Users, href: '/agents' },
  { name: '热门话题监控', icon: MessageCircle, href: '/groupchat' },
  { name: '社交平台实验室', icon: FlaskConical, href: '/experiments' },
  { name: '系统日志', icon: MessageSquare, href: '/logs' },
  { name: '系统设置', icon: SettingsIcon, href: '/settings' },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation()

  return (
    <div className="flex h-screen bg-bg-primary text-text-primary font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-bg-secondary border-r border-border-default flex flex-col z-20">
        <div className="p-6 flex items-center gap-3">
          <Logo />
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto custom-scrollbar">
          {navItems.map(item => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 group relative',
                  isActive
                    ? 'bg-accent-subtle text-accent'
                    : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                )}
              >
                <item.icon
                  className={cn(
                    'w-5 h-5 transition-transform group-hover:scale-110',
                    isActive && 'text-accent'
                  )}
                />
                {item.name}
                {isActive && (
                  <motion.div
                    layoutId="active-nav"
                    className="absolute left-0 w-1 h-6 bg-accent rounded-r-full"
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t border-border-default">
          <div className="bg-bg-tertiary/50 rounded-2xl p-4 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-accent text-xs font-bold">
              AD
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold truncate">Admin User</p>
              <p className="text-[10px] text-text-tertiary truncate">a4098853@gmail.com</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto relative custom-scrollbar">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,0.05),transparent_50%)] pointer-events-none"></div>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="relative z-10 h-full"
        >
          {children}
        </motion.div>
      </main>
    </div>
  )
}
