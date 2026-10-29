import React from 'react';
import { NavLink } from 'react-router-dom';
import { Button } from '../components/common/Button';
import { AlertCircle, Home } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center p-6">
      <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mb-4 border border-rose-100">
        <AlertCircle className="w-8 h-8" />
      </div>
      <h1 className="text-3xl font-bold text-slate-800 tracking-tight">404 - Page Not Found</h1>
      <p className="text-slate-500 mt-2 max-w-md text-sm">
        The page you are looking for does not exist in MediShop or has been moved.
      </p>
      <div className="mt-6">
        <NavLink to="/dashboard">
          <Button variant="primary" icon={Home}>
            Return to Dashboard
          </Button>
        </NavLink>
      </div>
    </div>
  );
}
