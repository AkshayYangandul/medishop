import { useNavigate, NavLink } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { loginSchema } from '../schemas/authSchema';
import { Cross, Lock, Mail, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react';
import { Button } from '../components/common/Button';

export function LoginPage() {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: 'pharmacist@medishop.local',
      password: 'password123',
      rememberMe: true,
    },
  });

  const onSubmit = () => {
    // Phase 1: Authentication is simulated (No Supabase yet)
    setTimeout(() => {
      navigate('/dashboard');
    }, 400);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-brand-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 px-4">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        {/* Brand Icon */}
        <div className="mx-auto w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-brand-400 flex items-center justify-center text-white shadow-xl shadow-brand-500/25 mb-3">
          <Cross className="w-7 h-7 rotate-45 stroke-[2.5]" />
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight">
          MediShop Portal
        </h2>
        <p className="mt-1 text-sm text-slate-400">
          Medical Store & Pharmacy Management Suite
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-soft-xl rounded-2xl sm:px-10 border border-slate-100">
          {/* Phase 1 Advisory Alert */}
          <div className="mb-6 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <strong className="block font-semibold">Phase 1 Setup Demo</strong>
              <span>
                Backend authentication (Supabase) will be hooked up in Phase 2. Demo credentials are prefilled for testing.
              </span>
            </div>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Email Field */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Staff Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="email"
                  autoComplete="email"
                  {...register('email')}
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all placeholder:text-slate-400"
                  placeholder="name@pharmacy.com"
                />
              </div>
              {errors.email && (
                <p className="mt-1 text-xs text-rose-600 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input
                  type="password"
                  autoComplete="current-password"
                  {...register('password')}
                  className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all placeholder:text-slate-400"
                  placeholder="••••••••"
                />
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-rose-600 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Remember Me */}
            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-2 text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  {...register('rememberMe')}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
                />
                <span>Remember this terminal</span>
              </label>
              <span className="text-brand-600 hover:underline cursor-pointer">
                Forgot password?
              </span>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="w-full"
              disabled={isSubmitting}
              icon={ArrowRight}
              iconPosition="right"
            >
              {isSubmitting ? 'Verifying...' : 'Sign In to MediShop'}
            </Button>
          </form>

          {/* Direct jump to dashboard link */}
          <div className="mt-6 pt-5 border-t border-slate-100 text-center">
            <NavLink
              to="/dashboard"
              className="text-xs text-slate-500 hover:text-brand-600 font-medium inline-flex items-center gap-1"
            >
              Skip login & browse dashboard directly &rarr;
            </NavLink>
          </div>
        </div>
      </div>
    </div>
  );
}
