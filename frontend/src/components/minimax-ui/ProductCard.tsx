import React from 'react'
import { cn } from '@/lib/utils'
import { minimaxRadius, minimaxShadows } from '@/components/tokens/minimax-theme'

/**
 * ProductCard - MiniMax风格产品卡片（深色主题）
 * 20-24px 大圆角，深色背景，品牌蓝色阴影
 */
interface ProductCardProps {
  children: React.ReactNode
  className?: string
  size?: 'md' | 'lg'
  gradient?: boolean
  onClick?: () => void
}

export function ProductCard({
  children,
  className,
  size = 'lg',
  gradient = false,
  onClick,
}: ProductCardProps) {
  const radius = size === 'lg' ? minimaxRadius['2xl'] : minimaxRadius.xl
  const shadow = gradient ? minimaxShadows.brand : minimaxShadows.md

  return (
    <div
      className={cn(
        'bg-bg-secondary border border-border-default p-6 transition-all duration-200',
        onClick && 'cursor-pointer hover:border-border-strong',
        className
      )}
      style={{
        borderRadius: radius,
        boxShadow: shadow,
      }}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
