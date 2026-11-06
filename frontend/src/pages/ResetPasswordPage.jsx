import { useState, useEffect } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { Cross, Lock, Eye, EyeOff, AlertCircle, CheckCircle, ArrowRight } from 'lucide-react';
import { Button } from '../components/common/Button';
import { verifyResetToken, resetPassword, ApiError } from '../services/api';

const MIN_PASSWORD_LENGTH = 6;

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const rawToken = searchParams.get('token') || '';

  // Token verification state
  const [tokenState, setTokenState] = useState('verifying'); // 'verifying' | 'valid' | 'invalid'
  const [maskedEmail, setMaskedEmail] = useState('');
  const [tokenError, setTokenError] = useState('');

  // Form state
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [succeeded, setSucceeded] = useState(false);

  // Verify token on mount
  useEffect(() => {
    if (!rawToken) {
      setTokenState('invalid');
      setTokenError('No reset token was found in the URL. Please request a new password reset link.');
      return;
    }

    let cancelled = false;
    verifyResetToken(rawToken)
      .then((data) => {
        if (cancelled) return;
        setMaskedEmail(data.email || '');
        setTokenState('valid');
      })
      .catch((err) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? err.message
            : 'Unable to validate the reset link. Please request a new one.';
        setTokenError(message);
        setTokenState('invalid');
      });

    return () => { cancelled = true; };
  }, [rawToken]);

  function validateForm() {
    if (!password) return 'New password is required.';
    if (password.length < MIN_PASSWORD_LENGTH)
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters long.`;
    if (password !== confirm) return 'Passwords do not match.';
    return '';
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const err = validateForm();
    if (err) {
      setFormError(err);
      return;
    }
    setFormError('');
    setIsSubmitting(true);
    try {
      await resetPassword({ token: rawToken, newPassword: password });
      setSucceeded(true);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : 'Unable to reset password. Please try again or request a new link.';
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  // ── Shared shell ───────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-brand-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 px-4">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="mx-auto w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-brand-400 flex items-center justify-center text-white shadow-xl shadow-brand-500/25 mb-3">
          <Cross className="w-7 h-7 rotate-45 stroke-[2.5]" />
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight">MediShop Portal</h2>
        <p className="mt-1 text-sm text-slate-400">Medical Store &amp; Pharmacy Management Suite</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-soft-xl rounded-2xl sm:px-10 border border-slate-100">

          {/* ── Verifying ── */}
          {tokenState === 'verifying' && (
            <div className="text-center py-6">
              <div className="animate-spin inline-block w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full mb-4" />
              <p className="text-sm text-slate-500">Validating your reset link…</p>
            </div>
          )}

          {/* ── Invalid / Expired token ── */}
          {tokenState === 'invalid' && (
            <div className="text-center space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-rose-50 border border-rose-200 flex items-center justify-center">
                <AlertCircle className="w-7 h-7 text-rose-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Link unavailable</h3>
              <p className="text-sm text-slate-500 leading-relaxed">{tokenError}</p>
              <Link
                to="/forgot-password"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:underline mt-2"
              >
                Request a new reset link
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          )}

          {/* ── Success ── */}
          {tokenState === 'valid' && succeeded && (
            <div className="text-center space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-green-50 border border-green-200 flex items-center justify-center">
                <CheckCircle className="w-7 h-7 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Password updated!</h3>
              <p className="text-sm text-slate-500">
                Your password has been successfully reset. You can now sign in with your new credentials.
              </p>
              <Button
                variant="primary"
                size="md"
                className="w-full mt-2"
                onClick={() => navigate('/login', { replace: true })}
                icon={ArrowRight}
                iconPosition="right"
              >
                Sign In with New Password
              </Button>
            </div>
          )}

          {/* ── Reset form ── */}
          {tokenState === 'valid' && !succeeded && (
            <>
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-slate-900">Choose a new password</h3>
                {maskedEmail && (
                  <p className="mt-1 text-sm text-slate-500">
                    Setting a new password for <strong>{maskedEmail}</strong>
                  </p>
                )}
              </div>

              {formError && (
                <div className="mb-5 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-semibold">Error</strong>
                    <span>{formError}</span>
                  </div>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate className="space-y-5">
                {/* New password */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setFormError(''); }}
                      className="w-full pl-9 pr-10 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all placeholder:text-slate-400"
                      placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
                      disabled={isSubmitting}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      tabIndex={-1}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Confirm password */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Confirm New Password
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type={showConfirm ? 'text' : 'password'}
                      autoComplete="new-password"
                      value={confirm}
                      onChange={(e) => { setConfirm(e.target.value); setFormError(''); }}
                      className="w-full pl-9 pr-10 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all placeholder:text-slate-400"
                      placeholder="Re-enter new password"
                      disabled={isSubmitting}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      tabIndex={-1}
                      aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
                    >
                      {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {/* Live match indicator */}
                  {confirm.length > 0 && (
                    <p className={`mt-1 text-xs flex items-center gap-1 ${password === confirm ? 'text-green-600' : 'text-rose-600'}`}>
                      {password === confirm
                        ? <><CheckCircle className="w-3 h-3" /> Passwords match</>
                        : <><AlertCircle className="w-3 h-3" /> Passwords do not match</>
                      }
                    </p>
                  )}
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="w-full"
                  disabled={isSubmitting}
                  icon={ArrowRight}
                  iconPosition="right"
                >
                  {isSubmitting ? 'Updating password…' : 'Set New Password'}
                </Button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

