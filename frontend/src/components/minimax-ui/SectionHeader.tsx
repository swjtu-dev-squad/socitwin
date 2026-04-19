import { cn } from '@/lib/utils'

/**
 * SectionHeader - 科技风章节标题
 * 等宽字体 + 装饰线
 */
interface SectionHeaderProps {
  title: string
  description?: string
  className?: string
}

export function SectionHeader({ title, description, className }: SectionHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-6 relative pb-4', className)}>
      {/* 下划线装饰 */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          width: '100px',
          height: '2px',
          background: 'linear-gradient(90deg, #00f2ff 0%, rgba(0, 242, 255, 0.3) 100%)',
        }}
      />

      <div>
        <h2
          className="font-semibold tracking-wider"
          style={{
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: '20px',
            color: '#00f2ff',
            letterSpacing: '0.15em',
            lineHeight: '1.5',
          }}
        >
          {title}
        </h2>
        {description && (
          <p
            className="font-normal tracking-wide mt-1"
            style={{
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: '13px',
              color: '#71717a',
              letterSpacing: '0.05em',
            }}
          >
            {description}
          </p>
        )}
      </div>
    </div>
  )
}
