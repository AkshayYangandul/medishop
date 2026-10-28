import React from 'react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from 'recharts';
import { Card, CardHeader, CardContent } from '../common/Card';
import { PieChart as PieIcon } from 'lucide-react';
import { mockCategoryDistribution } from '../../services/sampleData';

const CustomPieTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const data = payload[0];
    return (
      <div className="bg-slate-900 text-white p-2.5 rounded-lg shadow-xl text-xs border border-slate-700">
        <span className="font-semibold">{data.name}</span>: {data.value} items
      </div>
    );
  }
  return null;
};

export function CategoryDistributionChart() {
  const totalItems = mockCategoryDistribution.reduce((acc, cur) => acc + cur.value, 0);

  return (
    <Card className="h-full flex flex-col">
      <CardHeader
        title="Inventory by Category"
        subtitle="Distribution of stock across therapeutic classes"
        icon={PieIcon}
      />
      <CardContent className="flex-1 flex flex-col justify-between pt-2">
        <div className="h-[200px] w-full relative flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip content={<CustomPieTooltip />} />
              <Pie
                data={mockCategoryDistribution}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={80}
                paddingAngle={3}
                dataKey="value"
              >
                {mockCategoryDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-xl font-bold text-slate-800">{totalItems}</span>
            <span className="text-[11px] text-slate-400 font-medium">Total SKUs</span>
          </div>
        </div>

        {/* Legend pills */}
        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-100">
          {mockCategoryDistribution.map((item) => (
            <div key={item.name} className="flex items-center gap-2 text-xs">
              <span
                className="w-2.5 h-2.5 rounded-sm shrink-0"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-slate-600 truncate">{item.name}</span>
              <span className="text-slate-400 font-medium ml-auto">{item.value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
