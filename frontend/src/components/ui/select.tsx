import * as React from 'react'
import { Check, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SelectContextValue {
  value: string
  onChange: (value: string) => void
  open: boolean
  setOpen: (open: boolean) => void
}

const SelectContext = React.createContext<SelectContextValue | undefined>(undefined)

const useSelectContext = () => {
  const context = React.useContext(SelectContext)
  if (!context) {
    throw new Error('Select components must be used within <Select>')
  }
  return context
}

export interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
  defaultValue?: string
}

export function Select({ value, onValueChange, children, defaultValue }: SelectProps) {
  const [internalValue, setInternalValue] = React.useState(defaultValue || '')
  const [open, setOpen] = React.useState(false)

  const currentValue = value !== undefined ? value : internalValue
  const handleChange = onValueChange || setInternalValue

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = () => setOpen(false)
    if (open) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [open])

  return (
    <SelectContext.Provider value={{ value: currentValue, onChange: handleChange, open, setOpen }}>
      <div className="relative">{children}</div>
    </SelectContext.Provider>
  )
}

export interface SelectTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  asChild?: boolean
}

export const SelectTrigger = React.forwardRef<HTMLDivElement, SelectTriggerProps>(
  ({ className, children, asChild = false, ...props }, ref) => {
    const { open, setOpen } = useSelectContext()

    const handleClick = (e: React.MouseEvent) => {
      e.stopPropagation()
      setOpen(!open)
    }

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement<any>, {
        onClick: handleClick,
        ref,
      })
    }

    return (
      <div
        ref={ref}
        className={cn(
          'flex h-10 w-full items-center justify-between rounded-md border border-border-default bg-bg-primary px-3 py-2 text-sm placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer',
          className
        )}
        onClick={handleClick}
        {...props}
      >
        {children}
        <ChevronDown className="h-4 w-4 opacity-50" />
      </div>
    )
  }
)
SelectTrigger.displayName = 'SelectTrigger'

export interface SelectValueProps {
  placeholder?: string
  value?: string
}

export function SelectValue({ placeholder, value }: SelectValueProps) {
  const contextValue = useSelectContext()
  const displayValue = value !== undefined ? value : contextValue.value
  return <span>{displayValue || placeholder}</span>
}

export interface SelectContentProps extends React.HTMLAttributes<HTMLDivElement> {}

export const SelectContent = React.forwardRef<HTMLDivElement, SelectContentProps>(
  ({ className, children, ...props }, ref) => {
    const { open } = useSelectContext()

    if (!open) return null

    return (
      <div
        ref={ref}
        className={cn(
          'absolute z-50 min-w-[8rem] overflow-hidden rounded-md border border-border-strong bg-bg-secondary text-text-primary shadow-md mt-1 max-h-96 overflow-y-auto',
          className
        )}
        onClick={e => e.stopPropagation()}
        {...props}
      >
        {children}
      </div>
    )
  }
)
SelectContent.displayName = 'SelectContent'

export interface SelectItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
}

export const SelectItem = React.forwardRef<HTMLDivElement, SelectItemProps>(
  ({ className, children, value, ...props }, ref) => {
    const { value: currentValue, onChange, setOpen } = useSelectContext()

    const handleClick = (e: React.MouseEvent) => {
      e.stopPropagation()
      onChange(value)
      setOpen(false)
    }

    const isSelected = currentValue === value

    return (
      <div
        ref={ref}
        className={cn(
          'tech-select-item relative flex w-full cursor-pointer select-none items-center py-1.5 pl-8 pr-2 text-sm outline-none transition-colors',
          isSelected && 'selected',
          className
        )}
        onClick={handleClick}
        data-value={value}
        {...props}
      >
        <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
          {isSelected && <Check className="h-4 w-4" />}
        </span>
        {children}
      </div>
    )
  }
)
SelectItem.displayName = 'SelectItem'

export interface SelectSeparatorProps extends React.HTMLAttributes<HTMLDivElement> {}

export const SelectSeparator = React.forwardRef<HTMLDivElement, SelectSeparatorProps>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('-mx-1 my-1 h-px bg-border-default', className)} {...props} />
  )
)
SelectSeparator.displayName = 'SelectSeparator'
