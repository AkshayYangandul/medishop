import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '../../utilities/cn';
import { Card } from './Card';

const colorThemes = {
  emerald: {
    iconBg: 'bg-emerald-50 text-emerald-600 border border-emerald-100',
    barBg: 'bg-emerald-500',
    badgePos: 'bg-emerald-50 text-emerald-700',
  },
  blue: {
    iconBg: 'bg-sky-50 text-sky-600 border border-sky-100',
    barBg: 'bg-sky-500',
    badgePos: 'bg-sky-50 text-sky-700',
  },
  amber: {
    iconBg: 'bg-amber-50 text-amber-600 border border-amber-100',
    barBg: 'bg-amber-500',
    badgePos: 'bg-amber-50 text-amber-700',
  },
  rose: {
    iconBg: 'bg-rose-50 text-rose-600 border border-rose-100',
    barBg: 'bg-rose-500',
    badgePos: 'bg-rose-50 text-rose-700',
  },
};

export function StatCard({
  title,
  value,
  trend,
  isPositive = true,
  comparison,
  icon: Icon,
  color = 'emerald',
  className,
}) {
  const theme = colorThemes[color] || colorThemes.emerald;

  return (
    <Card className={cn('relative p-5 hover:translate-y-[-2px] transition-all duration-200', className)}>
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
          <div className="text-2xl font-bold text-slate-900 tracking-tight">{value}</div>
        </div>
        {Icon && (
          <div className={cn('p-3 rounded-xl shadow-soft-sm', theme.iconBg)}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center gap-2 pt-3 border-t border-slate-100">
        {trend && (
          <span
            className={cn(
              'inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full',
              isPositive
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-rose-50 text-rose-700'
            )}
          >
            {isPositive ? (
              <TrendingUp className="w-3 h-3 text-emerald-600" />
            ) : (
              <TrendingDown className="w-3 h-3 text-rose-600" />
            )}
            {trend}
          </span>
        )}
        {comparison && (
          <span className="text-xs text-slate-500 truncate">{comparison}</span>
        )}
      </div>
    </Card>
  );
}
