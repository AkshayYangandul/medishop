import React, { useCallback, useEffect, useState } from 'react';
import { BarChart3, RefreshCw, TrendingUp, DollarSign, Pill, AlertCircle, Loader2 } from 'lucide-react';
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

  const calculateDates = (range) => {
    const today = new Date();
    const end = today.toISOString().split('T')[0];
    if (range === 'today') {
      return { start: end, end };
    }
    if (range === '7d') {
      const d = new Date();
      d.setDate(d.getDate() - 7);
      return { start: d.toISOString().split('T')[0], end };
    }
    if (range === '30d') {
      const d = new Date();
      d.setDate(d.getDate() - 30);
      return { start: d.toISOString().split('T')[0], end };
    }
    return { start: undefined, end: undefined };
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Financial & Inventory Analytics"
        subtitle="Gross margins, cost-of-goods-sold (COGS), operating expenses, and dispensing reports"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          <div className="flex items-center gap-2">
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
                    <tr key={med.id} className="hover:bg-slate-50/70 transition-colors">
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
