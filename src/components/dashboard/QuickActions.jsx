import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardContent } from '../common/Card';
import {
  Zap,
  PlusCircle,
  ShoppingCart,
  Truck,
  Users,
  FileBarChart,
} from 'lucide-react';

const actions = [
  {
    label: 'New Sale (POS)',
    description: 'Instant checkout counter',
    path: '/sales',
    icon: ShoppingCart,
    color: 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border-emerald-200',
  },
  {
    label: 'Add Medicine',
    description: 'Register new drug/SKU',
    path: '/medicines',
    icon: PlusCircle,
    color: 'bg-teal-50 text-teal-700 hover:bg-teal-100 border-teal-200',
  },
  {
    label: 'Purchase Entry',
    description: 'Inward batch from supplier',
    path: '/purchases',
    icon: Truck,
    color: 'bg-sky-50 text-sky-700 hover:bg-sky-100 border-sky-200',
  },
  {
    label: 'Add Customer',
    description: 'Patient / regular client',
    path: '/customers',
    icon: Users,
    color: 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border-indigo-200',
  },
  {
    label: 'Sales Report',
    description: 'Tax and profit summary',
    path: '/reports',
    icon: FileBarChart,
    color: 'bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-200',
  },
];

export function QuickActions() {
  const navigate = useNavigate();

  return (
    <Card>
      <CardHeader
        title="Quick Operations"
        subtitle="Frequently used pharmacy workflows"
        icon={Zap}
      />
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {actions.map((act) => {
            const Icon = act.icon;
            return (
              <button
                key={act.label}
                onClick={() => navigate(act.path)}
                className={`p-3.5 rounded-xl border text-left transition-all duration-150 flex flex-col justify-between group cursor-pointer ${act.color}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="p-2 rounded-lg bg-white/80 shadow-soft-sm group-hover:scale-105 transition-transform">
                    <Icon className="w-5 h-5" />
                  </span>
                </div>
                <div>
                  <h4 className="font-semibold text-sm leading-tight text-slate-800">
                    {act.label}
                  </h4>
                  <p className="text-xs text-slate-500 mt-0.5 leading-snug">
                    {act.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
