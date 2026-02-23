import React from 'react';
import { cn } from '@/lib/utils';

export const Card = ({ className, children, ...props }: { className?: string, children: React.ReactNode, [key: string]: any }) => (
  <div className={cn("rounded-2xl border border-zinc-800 bg-zinc-900 shadow-xl", className)} {...props}>
    {children}
  </div>
);

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'outline' | 'secondary' | 'destructive' }>(
  ({ className, variant = 'default', ...props }, ref) => {
    const variants = {
      default: "bg-emerald-600 text-white hover:bg-emerald-700",
      outline: "border border-zinc-800 bg-transparent hover:bg-zinc-800 text-zinc-100",
      secondary: "bg-zinc-800 text-zinc-100 hover:bg-zinc-700",
      destructive: "bg-rose-600 text-white hover:bg-rose-700",
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
        "flex h-10 w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm ring-offset-zinc-950 file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
);

export const Badge = ({ className, variant = 'default', children, ...props }: { className?: string, variant?: 'default' | 'secondary' | 'outline' | 'destructive', children: React.ReactNode, [key: string]: any }) => {
  const variants = {
    default: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
    secondary: "bg-zinc-800 text-zinc-400 border-zinc-700",
    outline: "border-zinc-800 text-zinc-500",
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
  return <div className="relative w-full">{children}</div>;
};
export const SelectTrigger = ({ className, children }: any) => (
  <div className={cn("flex h-10 w-full items-center justify-between rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm", className)}>{children}</div>
);
export const SelectValue = ({ placeholder }: any) => <span>{placeholder}</span>;
export const SelectContent = ({ children }: any) => <div className="hidden">{children}</div>;
export const SelectItem = ({ children }: any) => <div>{children}</div>;

export const Slider = ({ value, onValueChange, min, max, step, className }: any) => (
  <input 
    type="range" 
    min={min} 
    max={max} 
    step={step} 
    value={value[0]} 
    onChange={(e) => onValueChange([parseInt(e.target.value)])}
    className={cn("w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-emerald-500", className)}
  />
);

export const Table = ({ children }: any) => <table className="w-full text-left border-collapse">{children}</table>;
export const TableHeader = ({ children, className }: any) => <thead className={className}>{children}</thead>;
export const TableBody = ({ children }: any) => <tbody>{children}</tbody>;
export const TableHead = ({ children, className }: any) => <th className={cn("p-4 text-zinc-500 font-bold text-xs uppercase tracking-widest", className)}>{children}</th>;
export const TableRow = ({ children, className, onClick }: any) => <tr onClick={onClick} className={cn("border-b border-zinc-800", className)}>{children}</tr>;
export const TableCell = ({ children, className }: any) => <td className={cn("p-4 text-sm", className)}>{children}</td>;

export const Drawer = ({ children, open, onClose }: any) => open ? <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 backdrop-blur-sm">{children}</div> : null;
export const DrawerContent = ({ children, className }: any) => <div className={cn("w-full max-w-2xl bg-zinc-900 border-t border-zinc-800 rounded-t-3xl overflow-hidden animate-in slide-in-from-bottom duration-300", className)}>{children}</div>;
export const DrawerHeader = ({ children, className }: any) => <div className={cn("p-6", className)}>{children}</div>;
export const DrawerTitle = ({ children, className }: any) => <h2 className={cn("text-lg font-bold", className)}>{children}</h2>;
export const DrawerDescription = ({ children, className }: any) => <p className={cn("text-sm text-zinc-500", className)}>{children}</p>;
export const DrawerFooter = ({ children, className }: any) => <div className={cn("p-6 border-t border-zinc-800", className)}>{children}</div>;
export const DrawerClose = ({ children }: any) => children;

export const Switch = ({ checked, onCheckedChange, className }: any) => (
  <button 
    role="switch"
    aria-checked={checked}
    onClick={() => onCheckedChange?.(!checked)}
    className={cn(
      "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 disabled:cursor-not-allowed disabled:opacity-50",
      checked ? "bg-emerald-600" : "bg-zinc-700",
      className
    )}
  >
    <span className={cn(
      "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
      checked ? "translate-x-5" : "translate-x-0"
    )} />
  </button>
);
