import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Pill,
  Tags,
  Bookmark,
  Layers,
  Truck,
  PackagePlus,
  Users,
  ShoppingCart,
  Receipt,
  FileBarChart,
  Settings,
  X,
  Cross,
  Sparkles,
} from 'lucide-react';
import { cn } from '../utilities/cn';

const navigationGroups = [
  {
    title: 'Overview',
    items: [
      { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    title: 'Inventory Management',
    items: [
      { name: 'Medicines', path: '/medicines', icon: Pill },
      { name: 'Categories', path: '/categories', icon: Tags },
      { name: 'Brands', path: '/brands', icon: Bookmark },
      { name: 'Batches & Expiry', path: '/batches', icon: Layers },
    ],
  },
  {
    title: 'Procurement',
    items: [
      { name: 'Suppliers', path: '/suppliers', icon: Truck },
      { name: 'Purchases', path: '/purchases', icon: PackagePlus },
    ],
  },
  {
    title: 'Sales & Patients',
    items: [
      { name: 'Sales & POS', path: '/sales', icon: ShoppingCart },
      { name: 'Customers', path: '/customers', icon: Users },
    ],
  },
  {
    title: 'Finance & Insights',
    items: [
      { name: 'Expenses', path: '/expenses', icon: Receipt },
      { name: 'Reports', path: '/reports', icon: FileBarChart },
    ],
  },
  {
    title: 'System',
    items: [
      { name: 'Settings', path: '/settings', icon: Settings },
    ],
  },
];

export function Sidebar({ isOpen, onClose }) {
  const location = useLocation();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={cn(
          'fixed top-0 bottom-0 left-0 z-50 w-64 bg-slate-900 text-slate-300 flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:z-auto border-r border-slate-800',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand Header */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-slate-800/80 bg-slate-950/40">
          <NavLink to="/dashboard" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-brand-400 flex items-center justify-center text-white shadow-lg shadow-brand-500/20 group-hover:scale-105 transition-transform">
              <Cross className="w-5 h-5 rotate-45 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-white text-lg tracking-tight">MediShop</span>
                <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-400 border border-brand-500/30">
                  v1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 leading-none">Pharmacy ERP</p>
            </div>
          </NavLink>

          {/* Mobile close button */}
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation list */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
          {navigationGroups.map((group) => (
            <div key={group.title} className="space-y-1">
              <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                {group.title}
              </p>
              <div className="space-y-0.5 mt-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = location.pathname === item.path;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => {
                        if (window.innerWidth < 1024) onClose();
                      }}
                      className={cn(
                        'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150',
                        isActive
                          ? 'bg-brand-600 text-white shadow-soft-sm font-semibold'
                          : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                      )}
                    >
                      <Icon
                        className={cn(
                          'w-4 h-4 shrink-0 transition-colors',
                          isActive ? 'text-white' : 'text-slate-400'
                        )}
                      />
                      <span className="truncate">{item.name}</span>
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Phase 1 Status Banner at bottom */}
        <div className="p-3 border-t border-slate-800/80 bg-slate-950/30">
          <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 text-xs">
            <div className="flex items-center gap-2 text-brand-400 font-semibold mb-1">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Phase 1: Project Setup</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Clean architecture & navigation ready. Database integration in Phase 2.
            </p>
          </div>
        </div>
      </aside>
    </>
  );
}
