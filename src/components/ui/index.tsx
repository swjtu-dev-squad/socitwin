import React, { useRef, useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

export const Card = ({ className, children, ...props }: { className?: string, children: React.ReactNode, [key: string]: any }) => (
  <div className={cn("rounded-2xl border border-border-default bg-bg-secondary shadow-xl", className)} {...props}>
    {children}
  </div>
);

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'outline' | 'secondary' | 'destructive' | 'ghost' }>(
  ({ className, variant = 'default', ...props }, ref) => {
    const variants = {
      default: "bg-accent text-white hover:bg-accent-hover glow-effect",
      outline: "border border-border-default bg-transparent hover:bg-bg-tertiary text-text-primary",
      secondary: "bg-bg-tertiary text-text-primary hover:bg-bg-elevated",
      destructive: "bg-rose-600 text-white hover:bg-rose-700",
      ghost: "bg-transparent hover:bg-bg-tertiary/50 text-text-primary",
    };
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
          variants[variant],
          className
        )}
        {...props}
      />
    );
  }
);

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-xl border border-border-default bg-bg-primary px-3 py-2 text-sm text-text-primary ring-offset-bg-primary file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-text-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);

export const Badge = ({ className, variant = 'default', children, ...props }: { className?: string, variant?: 'default' | 'secondary' | 'outline' | 'destructive', children: React.ReactNode, [key: string]: any }) => {
  const variants = {
    default: "bg-accent-subtle text-accent border-accent/20",
    secondary: "bg-bg-tertiary text-text-secondary border-border-default",
    outline: "border-border-default text-text-tertiary",
    destructive: "bg-rose-500/10 text-rose-500 border-rose-500/20",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold transition-colors", variants[variant], className)} {...props}>
      {children}
    </span>
  );
};

// Simplified versions of other components
export const ScrollArea = ({ className, children }: { className?: string, children: React.ReactNode }) => (
  <div className={cn("overflow-auto custom-scrollbar", className)}>{children}</div>
);

export const Select = ({ children, value, onValueChange }: any) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Deep clone children to pass down props to nested components
  const enhanceChildren = (children: any): any => {
    return React.Children.map(children, (child) => {
      if (!React.isValidElement(child)) return child;

      const childType = child.type as any;
      const childName = childType.displayName || childType.name;

      // Pass props to specific component types
      if (childName === 'SelectTrigger' || childType === SelectTrigger) {
        return React.cloneElement(child, {
          isOpen,
          setIsOpen,
        } as any);
      }

      if (childName === 'SelectValue' || childType === SelectValue) {
        return React.cloneElement(child, {
          value,
          isOpen,
        } as any);
      }

      if (childName === 'SelectContent' || childType === SelectContent) {
        const enhancedContentChildren = enhanceChildren(child.props.children);
        return React.cloneElement(child, {
          isOpen,
          children: enhancedContentChildren,
        } as any);
      }

      if (childName === 'SelectItem' || childType === SelectItem) {
        return React.cloneElement(child, {
          onValueChange,
          setIsOpen,
        } as any);
      }

      // Recursively enhance nested children
      if (child.props && child.props.children) {
        return React.cloneElement(child, {
          children: enhanceChildren(child.props.children),
        } as any);
      }

      return child;
    });
  };

  return (
    <div ref={selectRef} className="relative w-full">
      {enhanceChildren(children)}
    </div>
  );
};
Select.displayName = 'Select';

export const SelectTrigger = ({ className, children, isOpen, setIsOpen }: any) => (
  <div
    className={cn(
      "flex h-10 w-full items-center justify-between rounded-xl border border-border-default bg-bg-primary px-3 py-2 text-sm text-text-primary cursor-pointer hover:border-border-strong transition-colors",
      isOpen && "ring-2 ring-accent border-accent",
      className
    )}
    onClick={() => setIsOpen(!isOpen)}
  >
    {children}
    <svg
      className={cn(
        "w-4 h-4 text-text-tertiary transition-transform",
        isOpen && "transform rotate-180"
      )}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
    </svg>
  </div>
);
SelectTrigger.displayName = 'SelectTrigger';

export const SelectValue = ({ placeholder, value, isOpen }: any) => (
  <span className={value ? "text-text-primary" : "text-text-tertiary"}>
    {value || placeholder}
  </span>
);
SelectValue.displayName = 'SelectValue';

export const SelectContent = ({ children, isOpen, className }: any) => {
  if (!isOpen) return null;

  return (
    <div className={cn(
      "absolute z-50 w-full mt-1 bg-bg-secondary border border-border-default rounded-xl shadow-xl max-h-60 overflow-auto glass-effect",
      className
    )}>
      {children}
    </div>
  );
};
SelectContent.displayName = 'SelectContent';

export const SelectItem = ({ children, value, onValueChange, setIsOpen }: any) => (
  <div
    className="px-3 py-2 text-sm text-text-secondary hover:bg-bg-tertiary hover:text-accent cursor-pointer transition-colors first:rounded-t-xl last:rounded-b-xl"
    onClick={(e) => {
      e.stopPropagation();
      onValueChange(value);
      setIsOpen(false);
    }}
  >
    {children}
  </div>
);
SelectItem.displayName = 'SelectItem';

export const Slider = ({ value, onValueChange, min, max, step, className }: any) => {
  const percentage = ((value[0] - min) / (max - min)) * 100;

  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      value={value[0]}
      onChange={(e) => onValueChange([parseInt(e.target.value)])}
      className={cn("w-full", className)}
      style={{ '--progress': `${percentage}%` } as any}
    />
  );
};

export const Table = ({ children }: any) => <table className="w-full text-left border-collapse">{children}</table>;
export const TableHeader = ({ children, className }: any) => <thead className={className}>{children}</thead>;
export const TableBody = ({ children }: any) => <tbody>{children}</tbody>;
export const TableHead = ({ children, className }: any) => <th className={cn("p-4 text-text-tertiary font-bold text-xs uppercase tracking-widest", className)}>{children}</th>;
export const TableRow = ({ children, className, onClick }: any) => <tr onClick={onClick} className={cn("border-b border-border-default", className)}>{children}</tr>;
export const TableCell = ({ children, className }: any) => <td className={cn("p-4 text-sm", className)}>{children}</td>;

export const Drawer = ({ children, open, onClose }: any) => open ? <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 backdrop-blur-sm">{children}</div> : null;
export const DrawerContent = ({ children, className }: any) => <div className={cn("w-full max-w-2xl bg-bg-secondary border-t border-border-default rounded-t-3xl overflow-hidden animate-in slide-in-from-bottom duration-300", className)}>{children}</div>;
export const DrawerHeader = ({ children, className }: any) => <div className={cn("p-6", className)}>{children}</div>;
export const DrawerTitle = ({ children, className }: any) => <h2 className={cn("text-lg font-bold", className)}>{children}</h2>;
export const DrawerDescription = ({ children, className }: any) => <p className={cn("text-sm text-text-tertiary", className)}>{children}</p>;
export const DrawerFooter = ({ children, className }: any) => <div className={cn("p-6 border-t border-border-default", className)}>{children}</div>;
export const DrawerClose = ({ children }: any) => children;

export const Switch = ({ checked, onCheckedChange, className }: any) => (
  <button
    role="switch"
    aria-checked={checked}
    onClick={() => onCheckedChange?.(!checked)}
    className={cn(
      "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-primary disabled:cursor-not-allowed disabled:opacity-50",
      checked ? "bg-accent" : "bg-bg-tertiary",
      className
    )}
  >
    <span className={cn(
      "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
      checked ? "translate-x-5" : "translate-x-0"
    )} />
  </button>
);

export const Progress = ({ value, className }: any) => (
  <div className={cn("relative w-full h-2 overflow-hidden rounded-full bg-bg-tertiary", className)}>
    <div
      className="h-full bg-gradient-to-r from-accent to-accent-light transition-all duration-300 ease-in-out"
      style={{ width: `${value}%` }}
    />
  </div>
);
