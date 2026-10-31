import React from 'react';
import { Card, CardHeader, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Clock } from 'lucide-react';
import { formatDate } from '../../utilities/formatters';
import { useDashboardData } from '../../hooks/useDashboardData';

export function ExpiringAlertsList() {
  const { expiringBatches, loading, error } = useDashboardData();

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Expiry Watchlist"
        subtitle="Batches expiring within 60 days requiring clearance"
        icon={Clock}
        action={
          <Badge variant="warning" size="sm" dot>
            {expiringBatches.length} items
          </Badge>
        }
      />
      <CardContent className="p-0 divide-y divide-slate-100 flex-1">
        {loading ? (
          <div className="px-5 py-8 flex items-center justify-center text-slate-500">
            <span className="w-5 h-5 rounded-full border-2 border-brand-200 border-t-brand-600 animate-spin" />
          </div>
        ) : error ? (
          <div className="px-5 py-8 text-center text-xs text-rose-600">{error}</div>
        ) : expiringBatches.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-slate-500">No batches expiring within 60 days.</div>
        ) : (
          expiringBatches.map((item) => {
            const isCritical = item.daysRemaining <= 20;
            return (
              <div
                key={item.id}
                className="px-5 py-3.5 hover:bg-slate-50/70 transition-colors flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-slate-800 truncate">{item.medicineName}</h4>
                    <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                      {item.batchNo}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                    <span>Exp: {formatDate(item.expiryDate)}</span>
                    <span>•</span>
                    <span>
                      Stock: <strong className="text-slate-700">{item.quantity}</strong>
                    </span>
                    <span className="hidden sm:inline">•</span>
                    <span className="hidden sm:inline">{item.supplier}</span>
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <Badge variant={isCritical ? 'danger' : 'warning'} size="sm">
                    {item.daysRemaining} days left
                  </Badge>
                </div>
              </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
