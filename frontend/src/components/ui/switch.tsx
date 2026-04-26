import React, { useState } from 'react'

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  checked?: boolean
  onCheckedChange?: (checked: boolean) => void
}

export const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(
  (
    { className = '', checked, defaultChecked = false, onCheckedChange, onChange, ...props },
    ref
  ) => {
    const [uncontrolledValue, setUncontrolledValue] = useState(defaultChecked)
    const controlled = checked !== undefined
    const checkedValue = controlled ? checked : uncontrolledValue

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const newChecked = e.target.checked
      if (!controlled) {
        setUncontrolledValue(newChecked)
      }
      onCheckedChange?.(newChecked)
      onChange?.(e)
    }

    return (
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          ref={ref}
          checked={checkedValue}
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
