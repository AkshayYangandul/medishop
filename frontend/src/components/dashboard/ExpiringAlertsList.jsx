import { Card, CardHeader, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Clock } from 'lucide-react';
import { mockExpiringBatches } from '../../services/sampleData';
import { formatDate } from '../../utilities/formatters';

export function ExpiringAlertsList() {
  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Expiry Watchlist"
        subtitle="Batches expiring within 60 days requiring clearance"
        icon={Clock}
        action={
          <Badge variant="warning" size="sm" dot>
            {mockExpiringBatches.length} items
          </Badge>
        }
      />
      <CardContent className="p-0 divide-y divide-slate-100 flex-1">
        {mockExpiringBatches.map((item) => {
          const isCritical = item.daysRemaining <= 20;
          return (
            <div
              key={item.id}
              className="px-5 py-3.5 hover:bg-slate-50/70 transition-colors flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-semibold text-slate-800 truncate">
                    {item.medicineName}
                  </h4>
                  <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                    {item.batchNo}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                  <span>Exp: {formatDate(item.expiryDate)}</span>
                  <span>•</span>
                  <span>
                    Stock: <strong className="text-slate-700">{item.quantity}</strong> {item.unit}
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
        })}
      </CardContent>
    </Card>
  );
}
