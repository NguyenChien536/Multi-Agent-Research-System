import React from 'react';

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'outline' | 'ghost', isLoading?: boolean }>(
  ({ className = '', variant = 'primary', isLoading, children, disabled, ...props }, ref) => {
    const baseStyle = "inline-flex items-center justify-center rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-950 disabled:pointer-events-none disabled:opacity-50";
    const variants = {
      primary: "bg-zinc-900 text-zinc-50 hover:bg-zinc-900/90 shadow",
      outline: "border border-zinc-200 bg-white hover:bg-zinc-100 hover:text-zinc-900",
      ghost: "hover:bg-zinc-100 hover:text-zinc-900",
    };

    return (
      <button
        ref={ref}
        className={`${baseStyle} ${variants[variant]} h-10 px-4 py-2 ${className}`}
        disabled={isLoading || disabled}
        {...props}
      >
        {isLoading && (
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';
