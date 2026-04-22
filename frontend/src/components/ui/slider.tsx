import React from 'react'

export interface SliderProps {
  min?: number
  max?: number
  step?: number
  value?: number[]
  onValueChange?: (value: number[]) => void
  className?: string
}

export const Slider = React.forwardRef<HTMLInputElement, SliderProps>(
  ({ className = '', min = 0, max = 100, step = 1, value = [0], onValueChange, ...props }, ref) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = [parseFloat(e.target.value)]
      onValueChange?.(newValue)
    }

    // 计算进度百分比
    const progress = ((value[0] - min) / (max - min)) * 100

    return (
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value[0]}
        onChange={handleChange}
        className={`tech-slider ${className}`}
        ref={ref}
        style={
          {
            '--progress': `${progress}%`,
          } as React.CSSProperties
        }
        {...props}
      />
    )
  }
)
Slider.displayName = 'Slider'
