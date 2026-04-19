import React, { useState } from 'react'

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

export const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  ({ className = '', checked = false, onCheckedChange, onChange, ...props }, ref) => {
    const [internalChecked, setInternalChecked] = useState(checked)

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newChecked = e.target.checked
      setInternalChecked(newChecked)
      onCheckedChange?.(newChecked)
      onChange?.(e)
    }

    return (
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          ref={ref}
          checked={internalChecked}
          onChange={handleChange}
          className="sr-only peer"
          {...props}
        />
        <div
          className={`w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 ${className}`}
        />
      </label>
    )
  }
)
Switch.displayName = 'Switch'
