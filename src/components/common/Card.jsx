import React from 'react';
import { cn } from '../../utilities/cn';

export function Card({ children, className, ...props }) {
  return (
    <div
      className={cn(
        'bg-white rounded-xl border border-slate-200/80 shadow-soft-sm hover:shadow-soft-md transition-shadow duration-200 overflow-hidden',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className, title, subtitle, action, icon: Icon }) {
  if (!children && (title || subtitle || action || Icon)) {
    return (
      <div className={cn('px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-4', className)}>
        <div className="flex items-center gap-3">
          {Icon && (
            <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center border border-brand-100">
              <Icon className="w-5 h-5 text-brand-600" />
            </div>
          )}
          <div>
            {title && <h3 className="font-semibold text-slate-800 text-base">{title}</h3>}
            {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
          </div>
        </div>
        {action && <div>{action}</div>}
      </div>
    );
  }

  return (
    <div className={cn('px-5 py-4 border-b border-slate-100', className)}>
      {children}
    </div>
  );
}

export function CardContent({ children, className }) {
  return <div className={cn('p-5', className)}>{children}</div>;
}

export function CardFooter({ children, className }) {
  return (
    <div className={cn('px-5 py-3.5 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between', className)}>
      {children}
    </div>
  );
}
