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

export function Badge({
  className = '',
  children,
  variant = 'default',
}: {
  className?: string;
  children: React.ReactNode;
  variant?: 'default' | 'outline' | 'success' | 'danger' | 'purple';
}) {
  const dotColor =
    variant === 'success'
      ? 'bg-emerald-600'
      : variant === 'danger'
      ? 'bg-red-600'
      : variant === 'purple'
      ? 'bg-indigo-600'
      : variant === 'default'
      ? 'bg-blue-600'
      : null;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-100/90 text-zinc-800 border border-zinc-200 ${className}`}
    >
      {dotColor && <span className={`w-1.5 h-1.5 rounded-full ${dotColor} mr-1.5 shrink-0`} />}
      {children}
    </span>
  );
}
