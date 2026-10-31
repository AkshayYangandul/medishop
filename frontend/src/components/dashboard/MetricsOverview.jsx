import React from 'react';
import { Pill, AlertTriangle, CalendarClock, IndianRupee } from 'lucide-react';
import { StatCard } from '../common/StatCard';
import { formatCurrency, formatNumber } from '../../utilities/formatters';
import { useDashboardData } from '../../hooks/useDashboardData';

export function MetricsOverview() {
  const { metrics, loading, error } = useDashboardData();

  const totalMedicines = metrics?.totalMedicines ?? 0;
  const lowStockCount = metrics?.lowStockCount ?? 0;
  const expiringBatchesCount = metrics?.expiringBatchesCount ?? 0;
  const todayRevenue = metrics?.todaySales ?? 0;
  const todayOrders = metrics?.todayOrders ?? 0;

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-slate-200/80 shadow-soft-sm p-5 animate-pulse">
            <div className="h-3 w-24 bg-slate-200 rounded" />
            <div className="h-8 w-20 bg-slate-200 rounded mt-3" />
            <div className="h-3 w-32 bg-slate-100 rounded mt-4" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-soft-sm p-5 text-sm text-slate-600">
        Unable to load dashboard metrics right now. {error}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Medicines */}
      <StatCard
        title="Total Medicines"
        value={formatNumber(totalMedicines)}
        trend="+12.5%"
        isPositive={true}
        comparison="vs last month"
        icon={Pill}
        color="blue"
      />

      {/* Low-Stock Medicines */}
      <StatCard
        title="Low-Stock Items"
        value={formatNumber(lowStockCount)}
        trend="needs restock"
        isPositive={false}
        comparison="below reorder point"
        icon={AlertTriangle}
        color="rose"
      />

      {/* Expiring Batches */}
      <StatCard
        title="Expiring Batches"
        value={formatNumber(expiringBatchesCount)}
        trend="within 60 days"
        isPositive={false}
        comparison="needs clearance"
        icon={CalendarClock}
        color="amber"
      />

      {/* Today's Sales */}
      <StatCard
        title="Today's Sales"
        value={formatCurrency(todayRevenue)}
        trend={todayOrders > 0 ? `${todayOrders} orders` : 'Live counter'}
        isPositive={true}
        comparison="billed today"
        icon={IndianRupee}
        color="emerald"
      />
    </div>
  );
}
