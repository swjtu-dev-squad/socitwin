import React from 'react'
import { cn } from '@/lib/utils'

/**
 * PillButton - MiniMax风格Pill按钮（深色主题）
 * 9999px完全圆角
 */
interface PillButtonProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'primary' | 'secondary'
  size?: 'sm' | 'md'
  onClick?: () => void
  disabled?: boolean
}

export function PillButton({
  children,
  className,
  variant = 'default',
  size = 'md',
  onClick,
  disabled = false,
}: PillButtonProps) {
  const baseClasses =
    'inline-flex items-center justify-center font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed'

  const sizeClasses = {
    sm: 'px-4 py-2 text-xs',
    md: 'px-5 py-2.5 text-sm',
  }

  const variantClasses = {
    default: 'bg-[#3f3f46] text-[#fafafa] hover:bg-[#52525b] border border-[#3f3f46]',
    primary: 'bg-[#3b82f6] text-white hover:bg-[#2563eb] border border-transparent',
    secondary: 'bg-[#27272a] text-[#fafafa] hover:bg-[#3f3f46] border border-[#3f3f46]',
  }

  const classes = cn(baseClasses, sizeClasses[size], variantClasses[variant], className)

  return (
    <button
      className={classes}
      style={{
        borderRadius: '9999px',
        fontFamily: 'DM Sans, sans-serif',
        fontWeight: 500,
      }}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  )
}
