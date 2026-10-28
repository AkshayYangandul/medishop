import { NavLink } from 'react-router-dom';
import {
  Menu,
  Search,
  Bell,
  Building2,
  LogOut,
  ShieldCheck,
} from 'lucide-react';

export function Navbar({ onToggleSidebar }) {
  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-4 sm:px-6 flex items-center justify-between gap-4 sticky top-0 z-30 shadow-soft-sm">
      {/* Left section: Hamburger + Search */}
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <button
          onClick={onToggleSidebar}
          className="lg:hidden p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Search Bar */}
        <div className="relative w-full hidden sm:block">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Quick search medicines, batches, customers..."
            className="w-full pl-9 pr-4 py-2 bg-slate-100/80 hover:bg-slate-100 focus:bg-white text-sm rounded-lg border border-transparent focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all placeholder:text-slate-400"
          />
        </div>
      </div>

      {/* Right section: Store Info + Alerts + Profile */}
      <div className="flex items-center gap-3">
        {/* Pharmacy Branch Indicator */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-100 text-xs">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <Building2 className="w-3.5 h-3.5 text-emerald-700" />
          <span className="font-semibold text-emerald-800">Main Pharmacy Counter</span>
        </div>

        {/* Notification Bell */}
        <div className="relative">
          <button
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors relative"
            title="Notifications & Alerts"
          >
            <Bell className="w-5 h-5" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white" />
          </button>
        </div>

        {/* Divider */}
        <div className="h-6 w-px bg-slate-200" />

        {/* User Profile / Pharmacist Info */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:block text-right">
            <div className="text-xs font-semibold text-slate-800 flex items-center justify-end gap-1">
              <span>Dr. Rajesh Varma</span>
              <ShieldCheck className="w-3.5 h-3.5 text-brand-600" />
            </div>
            <p className="text-[11px] text-slate-400">Chief Pharmacist</p>
          </div>

          <div className="w-9 h-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-xs ring-2 ring-brand-500/20">
            RV
          </div>

          <NavLink
            to="/login"
            className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
            title="Go to Login / Logout"
          >
            <LogOut className="w-4 h-4" />
          </NavLink>
        </div>
      </div>
    </header>
  );
}
