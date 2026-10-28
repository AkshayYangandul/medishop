import React from 'react';
import { Pill, AlertTriangle, CalendarClock, IndianRupee } from 'lucide-react';
import { StatCard } from '../common/StatCard';
import { mockDashboardMetrics } from '../../services/sampleData';
import { formatCurrency, formatNumber } from '../../utilities/formatters';

export function MetricsOverview() {
  const { totalMedicines, lowStockCount, expiringBatchesCount, todaySales } = mockDashboardMetrics;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Medicines */}
      <StatCard
        title="Total Medicines"
        value={formatNumber(totalMedicines.value)}
        trend={totalMedicines.trend}
        isPositive={totalMedicines.isPositive}
        comparison={totalMedicines.comparison}
        icon={Pill}
        color="blue"
      />

      {/* Low-Stock Medicines */}
      <StatCard
        title="Low-Stock Items"
        value={formatNumber(lowStockCount.value)}
        trend={lowStockCount.trend}
        isPositive={lowStockCount.isPositive}
        comparison={lowStockCount.comparison}
        icon={AlertTriangle}
        color="rose"
      />

      {/* Expiring Batches */}
      <StatCard
        title="Expiring Batches"
        value={formatNumber(expiringBatchesCount.value)}
        trend={expiringBatchesCount.trend}
        isPositive={expiringBatchesCount.isPositive}
        comparison={expiringBatchesCount.comparison}
        icon={CalendarClock}
        color="amber"
      />

      {/* Today's Sales */}
      <StatCard
        title="Today's Sales"
        value={formatCurrency(todaySales.value)}
        trend={todaySales.trend}
        isPositive={todaySales.isPositive}
        comparison={todaySales.comparison}
        icon={IndianRupee}
        color="emerald"
      />
    </div>
  );
}
