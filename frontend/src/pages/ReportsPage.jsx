import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3,
  RefreshCw,
  TrendingUp,
  DollarSign,
  Pill,
  AlertCircle,
  Loader2,
  Download,
  CheckCircle2,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent, CardHeader } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { getReportsSummary } from '../services/api';
import { formatCurrency, formatNumber } from '../utilities/formatters';

export function ReportsPage() {
  const [dateRange, setDateRange] = useState('30d'); // 'today' | '7d' | '30d' | 'all'
  const [summary, setSummary] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(null);
  const [exportError, setExportError] = useState(null);

  const calculateDates = (range) => {
    const today = new Date();
    const end = today.toISOString().split('T')[0];
    if (range === 'today') {
      return { start: end, end, label: 'Today' };
    }
    if (range === '7d') {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      return { start: d.toISOString().split('T')[0], end, label: 'Last 7 Days' };
    }
    if (range === '30d') {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      return { start: d.toISOString().split('T')[0], end, label: 'Last 30 Days' };
    }
    return { start: undefined, end: undefined, label: 'All Time' };
  };

  const loadReport = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { start, end } = calculateDates(dateRange);
      const data = await getReportsSummary({ startDate: start, endDate: end });
      setSummary(data);
    } catch (err) {
      setError(err?.message || 'Failed to generate financial reports.');
    } finally {
      setIsLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const revenue = summary?.total_revenue ?? 0;
  const cogs = summary?.total_cogs ?? 0;
  const grossProfit = summary?.gross_profit ?? 0;
  const margin = summary?.gross_margin_percent ?? 0;
  const expenses = summary?.total_expenses ?? 0;
  const netProfit = summary?.net_profit ?? 0;
  const invoicesCount = summary?.total_invoices ?? 0;
  const topMeds = summary?.top_medicines || [];

  const handleExportReport = () => {
    if (!summary) return;
    setIsExporting(true);
    setExportError(null);
    setExportSuccess(null);

    try {
      const todayStr = new Date().toISOString().split('T')[0];
      const filename = `medishop_reports_${todayStr}.csv`;
      const { label, start, end } = calculateDates(dateRange);

      const csvRows = [];

      // 1. Title & Metadata
      csvRows.push(['MEDISHOP PHARMACY - FINANCIAL & DISPENSING ANALYTICS REPORT']);
      csvRows.push(['Selected Reporting Period', label]);
      csvRows.push(['Date Range Filters', start && end ? `${start} to ${end}` : 'Complete Cumulative History']);
      csvRows.push(['Report Generated At', new Date().toLocaleString()]);
      csvRows.push([]);

      // 2. Financial Metrics
      csvRows.push(['FINANCIAL SUMMARY & PROFIT/LOSS']);
      csvRows.push(['Metric', 'Amount / Value', 'Notes']);
      csvRows.push(['Gross Sales Revenue', `$${Number(revenue).toFixed(2)}`, `${invoicesCount} total sales invoices billed`]);
      csvRows.push(['Cost of Goods Sold (COGS)', `$${Number(cogs).toFixed(2)}`, 'Acquisition cost at time of sale']);
      csvRows.push(['Gross Profit', `$${Number(grossProfit).toFixed(2)}`, 'Gross Sales minus COGS']);
      csvRows.push(['Gross Margin Percentage', `${margin}%`, 'Gross Profit / Gross Revenue * 100']);
      csvRows.push(['Operating Expenses', `$${Number(expenses).toFixed(2)}`, 'Store utilities, rent, salaries & overhead']);
      csvRows.push(['Net Operating Profit', `$${Number(netProfit).toFixed(2)}`, 'Gross Profit minus Operating Expenses']);
      csvRows.push(['Total Sales Invoices Count', invoicesCount, 'Paid/completed customer counter bills']);
      csvRows.push([]);

      // 3. Top High-Velocity Medicines
      csvRows.push(['TOP HIGH-VELOCITY DISPENSED MEDICINES']);
      csvRows.push(['Rank', 'Medicine Name', 'Dosage Form', 'Units Dispensed', 'Revenue Generated']);
      if (topMeds.length > 0) {
        topMeds.forEach((med, idx) => {
          csvRows.push([
            idx + 1,
            med.name || '',
            med.dosage_form || '',
            med.quantity_sold ?? 0,
            `$${Number(med.revenue ?? 0).toFixed(2)}`,
          ]);
        });
      } else {
        csvRows.push(['No dispensed medicines recorded for this reporting period', '', '', '', '']);
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

      setExportSuccess(`Report successfully downloaded as ${filename}`);
      setTimeout(() => setExportSuccess(null), 5000);
    } catch (err) {
      setExportError(err?.message || 'Failed to export report.');
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

      <PageHeader
        title="Financial & Inventory Analytics"
        subtitle="Gross margins, cost-of-goods-sold (COGS), operating expenses, and dispensing reports"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1 text-xs font-semibold">
              <button
                onClick={() => setDateRange('today')}
                className={`px-3 py-1 rounded-md transition-colors ${
                  dateRange === 'today' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Today
              </button>
              <button
                onClick={() => setDateRange('7d')}
                className={`px-3 py-1 rounded-md transition-colors ${
                  dateRange === '7d' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Last 7 Days
              </button>
              <button
                onClick={() => setDateRange('30d')}
                className={`px-3 py-1 rounded-md transition-colors ${
                  dateRange === '30d' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Last 30 Days
              </button>
              <button
                onClick={() => setDateRange('all')}
                className={`px-3 py-1 rounded-md transition-colors ${
                  dateRange === 'all' ? 'bg-brand-600 text-white' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                All Time
              </button>
            </div>

            <Button
              variant="outline"
              size="sm"
              icon={Download}
              disabled={isLoading || isExporting || !summary}
              onClick={handleExportReport}
            >
              {isExporting ? <Loader2 className="w-4 h-4 animate-spin mr-1.5 inline" /> : null}
              Export Reports
            </Button>

            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={loadReport}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </div>
        }
      />

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Gross Revenue */}
        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Gross Sales Revenue</span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            {formatCurrency(revenue)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {invoicesCount} invoices billed in period
          </div>
        </div>

        {/* Cost of Goods Sold (COGS) */}
        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Cost of Goods Sold (COGS)</span>
            <span className="text-xs font-semibold text-slate-400">Lot Cost</span>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            {formatCurrency(cogs)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Gross Margin: {margin}% ({formatCurrency(grossProfit)})
          </div>
        </div>

        {/* Store Operating Expenses */}
        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Store Operating Expenses</span>
            <span className="text-xs font-semibold text-rose-500">Overhead</span>
          </div>
          <div className="text-2xl font-bold text-slate-900 mt-2">
            {formatCurrency(expenses)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Utilities, salaries &amp; rent
          </div>
        </div>

        {/* Net Operating Profit */}
        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="flex items-center justify-between text-xs text-slate-500 font-medium">
            <span>Net Store Profit</span>
            <TrendingUp className={`w-4 h-4 ${netProfit >= 0 ? 'text-emerald-600' : 'text-rose-600'}`} />
          </div>
          <div className={`text-2xl font-bold mt-2 ${netProfit >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
            {formatCurrency(netProfit)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Gross Profit minus Operating Outflows
          </div>
        </div>
      </div>

      {/* Top 10 Dispensed Products Table */}
      <Card>
        <CardHeader
          title="Top 10 High-Velocity Dispensed Medicines"
          subtitle="Ranked by total quantity units dispensed from counter POS"
          icon={Pill}
        />
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th className="py-3 px-5 font-semibold text-center w-14">Rank</th>
                  <th className="py-3 px-4 font-semibold">Medicine Name</th>
                  <th className="py-3 px-4 font-semibold">Dosage Formulation</th>
                  <th className="py-3 px-4 font-semibold text-center">Units Sold</th>
                  <th className="py-3 px-5 font-semibold text-right">Revenue Generated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Compiling sales analytics...
                    </td>
                  </tr>
                ) : topMeds.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      <BarChart3 className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      No sales recorded for this date window. Dispense counter orders to generate reports.
                    </td>
                  </tr>
                ) : (
                  topMeds.map((med, idx) => (
                    <tr key={med.id || idx} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-5 text-center font-bold text-slate-400">
                        #{idx + 1}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-900">
                        {med.name}
                      </td>
                      <td className="py-3.5 px-4">
                        <Badge variant="neutral" size="sm">
                          {med.dosage_form}
                        </Badge>
                      </td>
                      <td className="py-3.5 px-4 text-center font-semibold text-slate-800">
                        {formatNumber(med.quantity_sold)}
                      </td>
                      <td className="py-3.5 px-5 text-right font-semibold text-slate-900">
                        {formatCurrency(med.revenue)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
export default ReportsPage;
