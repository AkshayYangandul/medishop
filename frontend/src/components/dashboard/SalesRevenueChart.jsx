import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { Card, CardHeader, CardContent } from '../common/Card';
import { TrendingUp } from 'lucide-react';
import { formatCurrency } from '../../utilities/formatters';
import { useDashboardData } from '../../hooks/useDashboardData';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-xs space-y-1.5 border border-slate-700">
        <p className="font-semibold text-slate-200">{label}</p>
        {payload.map((entry, index) => (
          <div key={`item-${index}`} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-slate-300">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: entry.color }}
              />
              {entry.name}:
            </span>
            <span className="font-semibold text-white">
              {entry.name.includes('Revenue') ? formatCurrency(entry.value) : entry.value}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export function SalesRevenueChart() {
  const { stats, loading } = useDashboardData();
  const rawTrend = stats?.sales_trend || [];

  const trendData = rawTrend.map((item) => {
    const d = new Date(item.date);
    const dayLabel = isNaN(d.getTime())
      ? item.date
      : d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    return {
      day: dayLabel,
      revenue: item.revenue,
      orders: item.orders,
    };
  });

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Sales & Counter Revenue Trend"
        subtitle="7-day gross counter sales revenue"
        icon={TrendingUp}
        action={
          <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md font-medium">
            Live 7-Day Window
          </span>
        }
      />
      <CardContent className="flex-1 pt-4">
        {loading ? (
          <div className="h-[280px] flex items-center justify-center text-xs text-slate-400">
            Loading sales trends...
          </div>
        ) : trendData.length === 0 ? (
          <div className="h-[280px] flex items-center justify-center text-xs text-slate-400 text-center px-4">
            No sales recorded during this window. Sales billed at POS will graph automatically.
          </div>
        ) : (
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={trendData}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="colorSalesRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="day"
                  tickLine={false}
                  stroke="#94a3b8"
                  fontSize={11}
                  dy={6}
                />
                <YAxis
                  tickLine={false}
                  stroke="#94a3b8"
                  fontSize={11}
                  tickFormatter={(value) => `₹${value}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  verticalAlign="top"
                  align="right"
                  iconType="circle"
                  wrapperStyle={{ paddingBottom: '12px', fontSize: '12px' }}
                />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  name="Sales Revenue"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#colorSalesRevenue)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
