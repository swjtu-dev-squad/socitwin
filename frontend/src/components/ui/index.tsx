import * as React from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

// Card
export const Card = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("rounded-3xl border bg-card text-card-foreground shadow-sm", className)} {...props} />
)

// Button
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link'
  size?: 'default' | 'sm' | 'lg' | 'icon'
}
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    const variants = {
      default: "bg-accent text-bg-primary hover:bg-accent-hover shadow-lg shadow-accent/10",
      destructive: "bg-rose-500 text-white hover:bg-rose-600",
      outline: "border border-border-default bg-transparent hover:bg-bg-tertiary text-text-primary",
      secondary: "bg-bg-tertiary text-text-primary hover:bg-border-strong",
      ghost: "hover:bg-bg-tertiary text-text-secondary hover:text-text-primary",
      link: "text-accent underline-offset-4 hover:underline",
    }
    const sizes = {
      default: "h-11 px-6 py-2",
      sm: "h-9 px-4 rounded-xl text-xs",
      lg: "h-14 px-10 rounded-2xl text-base",
      icon: "h-10 w-10",
    }
    return (
      <button
        className={cn(
          "inline-flex items-center justify-center rounded-xl text-sm font-bold ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]",
          variants[variant],
          sizes[size],
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)

// Badge
export const Badge = ({ className, variant = 'default', ...props }: React.HTMLAttributes<HTMLDivElement> & { variant?: 'default' | 'secondary' | 'destructive' | 'outline' }) => {
  const variants = {
    default: "bg-accent/10 text-accent border-accent/20",
    secondary: "bg-bg-tertiary text-text-secondary border-border-default",
    destructive: "bg-rose-500/10 text-rose-500 border-rose-500/20",
    outline: "text-text-tertiary border-border-default",
  }
  return (
    <div className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2", variants[variant], className)} {...props} />
  )
}

// Slider (Minimal implementation)
export const Slider = ({ value, onValueChange, min, max, step, className }: { value: number[], onValueChange: (v: number[]) => void, min: number, max: number, step: number, className?: string }) => (
  <input
    type="range"
    min={min}
    max={max}
    step={step}
    value={value[0]}
    onChange={(e) => onValueChange([parseInt(e.target.value)])}
    className={cn("w-full h-1.5 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent", className)}
  />
)

// Progress
export const Progress = ({ value, className }: { value: number, className?: string }) => (
  <div className={cn("relative h-2 w-full overflow-hidden rounded-full bg-bg-tertiary", className)}>
    <div
      className="h-full w-full flex-1 bg-accent transition-all duration-500 ease-in-out"
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </div>
)

// Input
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-11 w-full rounded-xl border border-border-default bg-bg-primary px-4 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20 focus-visible:border-accent disabled:cursor-not-allowed disabled:opacity-50 transition-all",
        className
      )}
      ref={ref}
      {...props}
    />
  )
)

// Select (Radix-like structure)
export const Select = ({ children, value, onValueChange }: { children: React.ReactNode, value?: string, onValueChange?: (v: string) => void }) => {
  const [open, setOpen] = React.useState(false);
  const [triggerRect, setTriggerRect] = React.useState({ top: 0, left: 0, width: 0 });
  const triggerRef = React.useRef<HTMLButtonElement>(null);

  const handleOpen = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setTriggerRect({
        top: rect.bottom + window.scrollY + 8,
        left: rect.left + window.scrollX,
        width: rect.width
      });
    }
    setOpen(!open);
  };

  return (
    <div className="relative w-full">
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<any>, {
            value,
            onValueChange,
            open,
            setOpen: handleOpen,
            triggerRef,
            triggerRect
          });
        }
        return child;
      })}
    </div>
  );
};

export const SelectTrigger = ({ className, children, open, setOpen, triggerRef }: any) => (
  <button
    ref={triggerRef}
    onClick={setOpen}
    className={cn(
      "flex h-11 w-full items-center justify-between rounded-xl border border-border-default bg-bg-primary px-4 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent disabled:cursor-not-allowed disabled:opacity-50 transition-all",
      className
    )}
  >
    {children}
    <div className={cn("transition-transform duration-200", open ? "rotate-180" : "")}>
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6"/></svg>
    </div>
  </button>
);

export const SelectValue = ({ placeholder, value }: any) => (
  <span className={cn("block truncate", !value && "text-text-muted")}>
    {value || placeholder}
  </span>
);

export const SelectContent = ({ children, open, setOpen, value, onValueChange, triggerRect }: any) => {
  if (!open) return null;

  const content = (
    <>
      <div className="fixed inset-0 z-[9998]" onClick={() => setOpen(false)} />
      <div
        className="fixed z-[9999] min-w-[8rem] overflow-hidden rounded-xl border border-border-default bg-bg-secondary p-1 text-text-primary shadow-xl animate-in fade-in zoom-in-95 max-h-[300px] overflow-y-auto"
        style={{
          top: `${triggerRect.top}px`,
          left: `${triggerRect.left}px`,
          width: `${triggerRect.width}px`
        }}
      >
        {React.Children.map(children, child => {
          if (React.isValidElement(child)) {
            const childProps = child.props as any;
            return React.cloneElement(child as React.ReactElement<any>, {
              active: childProps.value === value,
              onClick: () => {
                onValueChange?.(childProps.value);
                setOpen(false);
              }
            });
          }
          return child;
        })}
      </div>
    </>
  );

  return createPortal(content, document.body);
};

export const SelectItem = ({ children, value: _value, active, onClick }: any) => (
  <div
    onClick={onClick}
    className={cn(
      "relative flex w-full cursor-pointer select-none items-center rounded-lg py-2 px-3 text-sm outline-none transition-colors hover:bg-bg-tertiary focus:bg-bg-tertiary",
      active && "bg-bg-tertiary text-accent font-bold"
    )}
  >
    <div className="flex flex-col gap-0.5">
      {children}
    </div>
    {active && (
      <div className="absolute right-3">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5"/></svg>
      </div>
    )}
  </div>
);

// Tabs
export const Tabs = ({ children, defaultValue, value: controlledValue, onValueChange, className }: { children: React.ReactNode, defaultValue?: string, value?: string, onValueChange?: (v: string) => void, className?: string }) => {
  const [internalValue, setInternalValue] = React.useState(defaultValue);
  const value = controlledValue !== undefined ? controlledValue : internalValue;
  const setValue = (v: string) => {
    if (controlledValue === undefined) setInternalValue(v);
    onValueChange?.(v);
  };
  return (
    <div className={cn("w-full", className)}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<any>, { value, setValue });
        }
        return child;
      })}
    </div>
  );
};

export const TabsList = ({ children, className, value, setValue }: any) => (
  <div className={cn("inline-flex h-10 items-center justify-center rounded-xl bg-bg-tertiary p-1 text-text-secondary", className)}>
    {React.Children.map(children, child => {
      if (React.isValidElement(child)) {
        const childProps = child.props as any;
        return React.cloneElement(child as React.ReactElement<any>, {
          active: childProps.value === value,
          onClick: () => setValue(childProps.value)
        });
      }
      return child;
    })}
  </div>
);

export const TabsTrigger = ({ children, value: _value, active, onClick, className }: any) => (
  <button
    onClick={onClick}
    className={cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
      active ? "bg-bg-primary text-text-primary shadow-sm" : "hover:text-text-primary",
      className
    )}
  >
    {children}
  </button>
);

export const TabsContent = ({ children, value: _value, active }: any) => {
  if (!active) return null;
  return <div className="mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">{children}</div>;
};

// Switch
export const Switch = ({ checked, onCheckedChange, className }: { checked: boolean, onCheckedChange: (v: boolean) => void, className?: string }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    onClick={() => onCheckedChange(!checked)}
    className={cn(
      "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/20 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
      checked ? "bg-accent" : "bg-bg-tertiary",
      className
    )}
  >
    <span
      className={cn(
        "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
        checked ? "translate-x-5" : "translate-x-0"
      )}
    />
  </button>
)

// ScrollArea
export const ScrollArea = React.forwardRef<HTMLDivElement, { children: React.ReactNode, className?: string }>(
  ({ children, className }, ref) => (
    <div ref={ref} className={cn("relative overflow-auto custom-scrollbar", className)}>
      {children}
    </div>
  )
)

// Table
export const Table = ({ className, ...props }: React.HTMLAttributes<HTMLTableElement>) => (
  <div className="relative w-full overflow-auto">
    <table className={cn("w-full caption-bottom text-sm", className)} {...props} />
  </div>
)
export const TableHeader = ({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) => (
  <thead className={cn("[&_tr]:border-b", className)} {...props} />
)
export const TableBody = ({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) => (
  <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />
)
export const TableRow = ({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) => (
  <tr className={cn("border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted", className)} {...props} />
)
export const TableHead = ({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
  <th className={cn("h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0", className)} {...props} />
)
export const TableCell = ({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
  <td className={cn("p-4 align-middle [&:has([role=checkbox])]:pr-0", className)} {...props} />
)
