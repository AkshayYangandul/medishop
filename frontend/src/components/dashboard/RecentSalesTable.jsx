import { Card, CardHeader } from '../common/Card';
import { Badge } from '../common/Badge';
import { ShoppingCart } from 'lucide-react';
import { mockRecentSales } from '../../services/sampleData';
import { formatCurrency } from '../../utilities/formatters';

export function RecentSalesTable() {
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
              <th className="py-3 px-4 font-semibold text-center">Items</th>
              <th className="py-3 px-4 font-semibold">Payment</th>
              <th className="py-3 px-4 font-semibold text-right">Amount</th>
              <th className="py-3 px-5 font-semibold text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {mockRecentSales.map((sale) => (
              <tr key={sale.id} className="hover:bg-slate-50/70 transition-colors">
                <td className="py-3 px-5 font-mono text-xs font-semibold text-slate-800">
                  {sale.id}
                  <div className="text-[11px] font-sans text-slate-400 font-normal">
                    {sale.time}
                  </div>
                </td>
                <td className="py-3 px-4">
                  <div className="font-medium text-slate-800">{sale.customerName}</div>
                  <div className="text-xs text-slate-400">{sale.customerPhone}</div>
                </td>
                <td className="py-3 px-4 text-center text-slate-600 font-medium">
                  {sale.itemsCount}
                </td>
                <td className="py-3 px-4">
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-100 font-medium text-slate-700">
                    {sale.paymentMethod}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-semibold text-slate-900">
                  {formatCurrency(sale.totalAmount)}
                </td>
                <td className="py-3 px-5 text-right">
                  <Badge variant="success" size="sm">
                    {sale.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
