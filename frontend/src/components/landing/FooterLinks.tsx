import { ExternalLink } from 'lucide-react'

// Icon placeholders for removed lucide-react icons
const Github = ExternalLink

export default function FooterLinks() {
  const links = [
    {
      name: 'CAMEL-AI',
      href: 'https://www.camel-ai.org/',
      icon: ExternalLink,
    },
    {
      name: 'Socitwin',
      href: 'https://github.com/your-org/socitwin',
      icon: Github,
    },
  ]

  return (
    <footer className="h-20 glass-effect border-t border-border-default">
      <div className="w-full max-w-7xl mx-auto px-6 lg:px-12 xl:px-16 h-full flex flex-col md:flex-row items-center justify-between gap-4">
        {/* 左侧：外部链接 */}
        <div className="flex items-center gap-6">
          {links.map(link => (
            <a
              key={link.name}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-xs text-text-muted hover:text-accent transition-colors duration-200 uppercase tracking-wider group"
            >
              <link.icon className="w-4 h-4 group-hover:scale-110 transition-transform" />
              <span className="group-hover:underline decoration-accent/50 underline-offset-4">
                {link.name}
              </span>
            </a>
          ))}
        </div>

        {/* 右侧：版本信息 */}
        <div className="flex items-center gap-2 text-xs text-text-muted font-mono">
          <span>v1.0.0</span>
          <span className="text-border-default">·</span>
          <span>Ready to Deploy</span>
        </div>
      </div>
    </footer>
  )
}
