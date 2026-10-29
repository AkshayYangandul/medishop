import React from 'react';
import { cn } from '../../utilities/cn';

const variants = {
  primary:
    'bg-brand-600 hover:bg-brand-700 text-white shadow-soft-sm hover:shadow-soft-md active:bg-brand-800 focus-visible:ring-brand-500',
  secondary:
    'bg-slate-100 hover:bg-slate-200 text-slate-700 active:bg-slate-300 focus-visible:ring-slate-400',
  outline:
    'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 hover:border-slate-400 active:bg-slate-100 focus-visible:ring-slate-400',
  danger:
    'bg-rose-600 hover:bg-rose-700 text-white shadow-soft-sm active:bg-rose-800 focus-visible:ring-rose-500',
  ghost:
    'bg-transparent hover:bg-slate-100 text-slate-600 hover:text-slate-900 focus-visible:ring-slate-400',
};

const sizes = {
  sm: 'text-xs px-2.5 py-1.5 gap-1.5 rounded-lg',
  md: 'text-sm px-4 py-2 gap-2 rounded-lg font-medium',
  lg: 'text-base px-5 py-2.5 gap-2.5 rounded-xl font-semibold',
  icon: 'p-2 rounded-lg',
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  className,
  disabled,
  ...props
}) {
  return (
    <button
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center font-medium transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {Icon && iconPosition === 'left' && <Icon className="w-4 h-4 shrink-0" />}
      {children}
      {Icon && iconPosition === 'right' && <Icon className="w-4 h-4 shrink-0" />}
    </button>
  );
}
