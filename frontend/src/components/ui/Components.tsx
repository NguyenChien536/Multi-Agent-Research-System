import React from 'react';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className = '', ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={`flex h-10 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm ring-offset-white file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export function Card({ className = '', children }: { className?: string, children: React.ReactNode }) {
  return <div className={`rounded-xl border border-zinc-200 bg-white text-zinc-950 shadow-sm ${className}`}>{children}</div>;
}

export function Badge({ className = '', children, variant = 'default' }: { className?: string, children: React.ReactNode, variant?: 'default'|'outline' }) {
  const base = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-950 focus:ring-offset-2";
  const variants = {
    default: "bg-zinc-900 text-zinc-50 hover:bg-zinc-900/80",
    outline: "text-zinc-950 border border-zinc-200"
  };
  return <div className={`${base} ${variants[variant]} ${className}`}>{children}</div>;
}
