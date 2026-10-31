import React from 'react';
import { Card, CardHeader } from '../common/Card';
import { Badge } from '../common/Badge';
import { ShoppingCart } from 'lucide-react';
import { formatCurrency } from '../../utilities/formatters';
import { useDashboardData } from '../../hooks/useDashboardData';

export function RecentSalesTable() {
  const { stats, loading } = useDashboardData();
  const sales = stats?.recent_sales || [];

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Recent Sales Invoices"
        subtitle="Latest checkout transactions from the counter"
        icon={ShoppingCart}
      />
      <div className="overflow-x-auto flex-1">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
            <tr>
              <th className="py-3 px-5 font-semibold">Invoice #</th>
              <th className="py-3 px-4 font-semibold">Customer</th>
              <th className="py-3 px-4 font-semibold">Payment</th>
              <th className="py-3 px-4 font-semibold text-right">Amount</th>
              <th className="py-3 px-5 font-semibold text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-400">
                  Loading recent sales...
                </td>
              </tr>
            ) : sales.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-400 text-sm">
                  No counter sales recorded yet. Invoices billed in POS will appear here.
                </td>
              </tr>
            ) : (
              sales.map((sale) => (
                <tr key={sale.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="py-3 px-5 font-mono text-xs font-semibold text-slate-800">
                    {sale.invoice_no}
                    <div className="text-[11px] font-sans text-slate-400 font-normal">
                      {sale.created_at ? new Date(sale.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="font-medium text-slate-800">{sale.customer_name}</div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-100 font-medium text-slate-700 uppercase">
                      {sale.payment_method}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-semibold text-slate-900">
                    {formatCurrency(sale.amount)}
                  </td>
                  <td className="py-3 px-5 text-right">
                    <Badge variant={sale.status === 'paid' ? 'success' : 'warning'} size="sm">
                      {sale.status}
                    </Badge>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
