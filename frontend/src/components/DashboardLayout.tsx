import { Link, useLocation } from 'react-router-dom'
import {
  UserRound,
  Users,
  MessageSquare,
  Settings as SettingsIcon,
  MessageCircle,
  Eye,
  FlaskConical,
  Activity,
} from 'lucide-react'
import { motion } from 'motion/react'
import { Logo } from './Logo'

const navItems = [
  {
    id: 'overview-v2',
    name: '态势推演 V2',
    icon: Eye,
    href: '/overview-v2',
  },
  {
    id: 'overview',
    name: '态势推演 (旧版)',
    icon: Activity,
    href: '/overview',
  },
  {
    id: 'profiles',
    name: '用户画像',
    icon: UserRound,
    href: '/profiles',
  },
  {
    id: 'agents',
    name: '社交网络监控',
    icon: Users,
    href: '/agents',
  },
  {
    id: 'groupchat',
    name: '热门话题监控',
    icon: MessageCircle,
    href: '/groupchat',
  },
  {
    id: 'experiments',
    name: '社交平台实验室',
    icon: FlaskConical,
    href: '/experiments',
  },
  {
    id: 'logs',
    name: '系统日志',
    icon: MessageSquare,
    href: '/logs',
  },
  {
    id: 'settings',
    name: '系统设置',
    icon: SettingsIcon,
    href: '/settings',
  },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation()

  return (
    <div className="flex h-screen font-sans overflow-hidden" style={{ background: '#181e25' }}>
      {/* Sidebar - 深色科技风 */}
      <aside
        className="w-64 flex flex-col z-20 relative"
        style={{
          background: 'rgba(24, 30, 37, 0.95)',
          backdropFilter: 'blur(20px)',
        }}
      >
        {/* Logo 区域 - 装饰角标 */}
        <div className="relative p-6">
          {/* 装饰角标 */}
          <div
            style={{
              position: 'absolute',
              top: '24px',
              left: '24px',
              width: '6px',
              height: '6px',
              borderTop: '1px solid rgba(0, 242, 255, 0.5)',
              borderLeft: '1px solid rgba(0, 242, 255, 0.5)',
            }}
          />
          <div className="flex items-center gap-3 pl-3">
            <Logo />
          </div>
        </div>

        {/* 导航区域 */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto custom-scrollbar">
          {navItems.map(item => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.href}
                to={item.href}
                className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 group relative"
                style={{
                  fontFamily: '"JetBrains Mono", monospace',
                  letterSpacing: '0.05em',
                  ...(isActive
                    ? {
                        background: 'rgba(0, 242, 255, 0.1)',
                        color: '#00f2ff',
                        border: '1px solid rgba(0, 242, 255, 0.3)',
                      }
                    : {
                        color: '#a1a1aa',
                      }),
                }}
                onMouseEnter={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)'
                    e.currentTarget.style.borderColor = 'rgba(59, 130, 246, 0.2)'
                    e.currentTarget.style.color = '#fafafa'
                  }
                }}
                onMouseLeave={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.borderColor = 'transparent'
                    e.currentTarget.style.color = '#a1a1aa'
                  }
                }}
              >
                {/* 图标 */}
                <item.icon
                  className="w-4 h-4 transition-transform group-hover:scale-110"
                  style={{
                    color: isActive ? '#00f2ff' : 'inherit',
                    flexShrink: 0,
                  }}
                />

                {/* 导航项名称 */}
                <span className="flex-1">{item.name}</span>

                {/* 激活状态指示器 */}
                {isActive && (
                  <motion.div
                    layoutId="active-nav"
                    className="absolute left-0 w-0.5 h-8 rounded-r-full"
                    style={{
                      background:
                        'linear-gradient(180deg, #00f2ff 0%, rgba(0, 242, 255, 0.3) 100%)',
                      boxShadow: '0 0 8px rgba(0, 242, 255, 0.6)',
                    }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}

                {/* 悬停时发光 */}
                {isActive && (
                  <div
                    className="absolute inset-0 rounded-lg pointer-events-none"
                    style={{
                      background:
                        'radial-gradient(circle at center, rgba(0, 242, 255, 0.1) 0%, transparent 70%)',
                    }}
                  />
                )}
              </Link>
            )
          })}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto relative custom-scrollbar">
        {/* 背景装饰 - 青色光晕 */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(circle at 50% 0%, rgba(0, 242, 255, 0.03) 0%, transparent 50%)',
          }}
        />
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
