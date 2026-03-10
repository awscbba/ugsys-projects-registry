import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { LoadingSpinner } from './LoadingSpinner';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
  children: ReactNode;
  className?: string;
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-[#FF9900] text-[#161d2b] hover:bg-[#ffb84d] focus-visible:ring-[#FF9900] shadow-[0_2px_12px_rgba(255,153,0,0.25)]',
  secondary:
    'bg-transparent text-white/70 border border-white/[0.12] hover:border-white/25 hover:text-white/90 hover:bg-white/[0.05] focus-visible:ring-white/30',
  danger:
    'bg-red-500/15 text-red-300 border border-red-500/25 hover:bg-red-500/25 focus-visible:ring-red-500',
  ghost:
    'text-white/50 hover:text-white/80 hover:bg-white/[0.06] focus-visible:ring-white/30',
};

const sizeClasses: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled,
  children,
  className = '',
  type = 'button',
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || isLoading;

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-disabled={isDisabled}
      className={[
        'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#161d2b]',
        'disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]',
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(' ')}
      {...rest}
    >
      {isLoading && <LoadingSpinner size="sm" className="shrink-0" />}
      {children}
    </button>
  );
}
