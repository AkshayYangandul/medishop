import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { MetricsOverview } from '../components/dashboard/MetricsOverview';
import { SalesRevenueChart } from '../components/dashboard/SalesRevenueChart';
import { CategoryDistributionChart } from '../components/dashboard/CategoryDistributionChart';
import { RecentSalesTable } from '../components/dashboard/RecentSalesTable';
import { ExpiringAlertsList } from '../components/dashboard/ExpiringAlertsList';
import { QuickActions } from '../components/dashboard/QuickActions';
import { ShoppingCart, Download, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useDashboardData } from '../hooks/useDashboardData';

export function DashboardPage() {
  const { metrics, stats, expiringBatches, loading: isDataLoading } = useDashboardData();
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(null);
  const [exportError, setExportError] = useState(null);

  const handleExportSummary = () => {
    setIsExporting(true);
    setExportError(null);
    setExportSuccess(null);

    try {
      const todayStr = new Date().toISOString().split('T')[0];
      const filename = `medishop_dashboard_summary_${todayStr}.csv`;

      const csvRows = [];

      // 1. Header Section
      csvRows.push(['MEDISHOP PHARMACY - EXECUTIVE DASHBOARD SUMMARY']);
      csvRows.push(['Export Generated At', new Date().toLocaleString()]);
      csvRows.push([]);

      // 2. Executive Key Metrics
      csvRows.push(['EXECUTIVE DASHBOARD METRICS']);
      csvRows.push(['Metric Name', 'Reported Value']);
      csvRows.push(["Today's Sales Revenue", `$${(metrics?.todaySales ?? 0).toFixed(2)}`]);
      csvRows.push(["Today's Order Transactions", metrics?.todayOrders ?? 0]);
      csvRows.push(['Active Medicines in Catalog', metrics?.totalMedicines ?? 0]);
      csvRows.push(['Low Stock Medicine Alerts', metrics?.lowStockCount ?? 0]);
      csvRows.push(['Expiring Batches (within threshold)', metrics?.expiringBatchesCount ?? 0]);
      csvRows.push([]);

      // 3. 7-Day Revenue Trend
      csvRows.push(['7-DAY SALES & REVENUE TREND']);
      csvRows.push(['Date', 'Orders', 'Gross Revenue']);
      if (stats?.revenue_chart && stats.revenue_chart.length > 0) {
        stats.revenue_chart.forEach((r) => {
          csvRows.push([
            r.date || '',
            r.orders ?? 0,
            `$${Number(r.revenue ?? 0).toFixed(2)}`,
          ]);
        });
      } else {
        csvRows.push(['No sales history recorded for this period', '', '']);
      }
      csvRows.push([]);

      // 4. Category Inventory Distribution
      csvRows.push(['INVENTORY DISTRIBUTION BY CATEGORY']);
      csvRows.push(['Category Name', 'Medicines Count']);
      if (stats?.category_distribution && stats.category_distribution.length > 0) {
        stats.category_distribution.forEach((c) => {
          csvRows.push([c.name || '', c.count ?? 0]);
        });
      } else {
        csvRows.push(['No category inventory records available', '']);
      }
      csvRows.push([]);

      // 5. Recent Sales Transactions
      csvRows.push(['RECENT SALES TRANSACTIONS']);
      csvRows.push([
        'Invoice No',
        'Customer Name',
        'Cashier / Staff',
        'Transaction Date',
        'Payment Method',
        'Payment Status',
        'Net Amount',
      ]);
      if (stats?.recent_sales && stats.recent_sales.length > 0) {
        stats.recent_sales.forEach((s) => {
          csvRows.push([
            s.invoice_no || '',
            s.customer_name || 'Walk-in Customer',
            s.cashier_name || 'Counter Staff',
            s.created_at ? new Date(s.created_at).toLocaleString() : '',
            (s.payment_method || '').toUpperCase(),
            (s.payment_status || '').toUpperCase(),
            `$${Number(s.net_amount ?? 0).toFixed(2)}`,
          ]);
        });
      } else {
        csvRows.push(['No recent transactions recorded', '', '', '', '', '', '']);
      }
      csvRows.push([]);

      // 6. Critical Expiry Alerts Watchlist
      csvRows.push(['EXPIRING BATCHES WATCHLIST']);
      csvRows.push([
        'Medicine Name',
        'Batch No',
        'Expiry Date',
        'Days Remaining',
        'Current Quantity',
        'Supplier',
      ]);
      if (expiringBatches && expiringBatches.length > 0) {
        expiringBatches.forEach((b) => {
          csvRows.push([
            b.medicineName || '',
            b.batchNo || '',
            b.expiryDate || '',
            b.daysRemaining ?? '',
            b.quantity ?? 0,
            b.supplier || 'N/A',
          ]);
        });
      } else {
        csvRows.push(['No batches currently expiring within the alert window', '', '', '', '', '']);
      }

      // Convert array of rows to CSV string with Excel UTF-8 BOM
      const csvContent =
        '\uFEFF' +
        csvRows
          .map((row) =>
            row
              .map((field) => {
                const str = String(field ?? '');
                return `"${str.replace(/"/g, '""')}"`;
              })
              .join(',')
          )
          .join('\r\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setExportSuccess(`Dashboard summary successfully downloaded as ${filename}`);
      setTimeout(() => setExportSuccess(null), 5000);
    } catch (err) {
      setExportError(err?.message || 'Failed to generate export file.');
      setTimeout(() => setExportError(null), 5000);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {exportSuccess && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2 text-emerald-800 text-xs font-semibold animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{exportSuccess}</span>
        </div>
      )}
      {exportError && (
        <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-center gap-2 text-rose-800 text-xs font-semibold animate-in fade-in">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {/* Page Header */}
      <PageHeader
        title="Pharmacy Dashboard"
        subtitle="Real-time overview of pharmacy inventory, counter sales, and batch expiry tracking."
        badge={
          <Badge variant="brand" size="md" dot>
            Live Operational Data
          </Badge>
        }
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              icon={Download}
              disabled={isExporting || isDataLoading}
              onClick={handleExportSummary}
            >
              {isExporting ? <Loader2 className="w-4 h-4 animate-spin mr-1.5 inline" /> : null}
              Export Summary
            </Button>
            <NavLink to="/sales">
              <Button variant="primary" size="sm" icon={ShoppingCart}>
                New Sale (POS)
              </Button>
            </NavLink>
          </>
        }
      />

      {/* Summary Stat Cards */}
      <MetricsOverview />

      {/* Quick Action Shortcuts */}
      <QuickActions />

      {/* Charts Section: Weekly Sales Area Chart + Category Donut Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <SalesRevenueChart />
        </div>
        <div className="lg:col-span-1">
          <CategoryDistributionChart />
        </div>
      </div>

      {/* Tables and Alerts: Recent Sales + Expiry Watchlist */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <RecentSalesTable />
        </div>
        <div className="lg:col-span-1">
          <ExpiringAlertsList />
        </div>
      </div>
    </div>
  );
}
export default DashboardPage;
