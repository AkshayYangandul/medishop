import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Cross, Mail, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';
import { Button } from '../components/common/Button';
import { requestPasswordReset, ApiError } from '../services/api';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState(null);

  function validateEmail(value) {
    if (!value.trim()) return 'Email address is required.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())) return 'Please enter a valid email address.';
    return '';
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const err = validateEmail(email);
    if (err) {
      setEmailError(err);
      return;
    }
    setEmailError('');
    setServerError(null);
    setIsSubmitting(true);
    try {
      await requestPasswordReset(email.trim().toLowerCase());
      setSubmitted(true);
    } catch (error) {
      // Surface generic message only — backend guarantees anti-enumeration
      const message =
        error instanceof ApiError
          ? error.message
          : 'Unable to reach the server. Please try again later.';
      setServerError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

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
          Medical Store &amp; Pharmacy Management Suite
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-soft-xl rounded-2xl sm:px-10 border border-slate-100">
          {submitted ? (
            /* Success state */
            <div className="text-center space-y-4">
              <div className="mx-auto w-14 h-14 rounded-full bg-green-50 border border-green-200 flex items-center justify-center">
                <CheckCircle className="w-7 h-7 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Check your email</h3>
              <p className="text-sm text-slate-500 leading-relaxed">
                If that email address is registered, password reset instructions have been sent.
                The link expires after <strong>30&nbsp;minutes</strong>.
              </p>
              <p className="text-xs text-slate-400">
                Check your spam folder if you don&apos;t see it within a few minutes.
              </p>
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline font-medium mt-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to Sign In
              </Link>
            </div>
          ) : (
            /* Request form */
            <>
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-slate-900">Reset your password</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Enter your registered staff email address and we&apos;ll send you a reset link.
                </p>
              </div>

              {serverError && (
                <div className="mb-5 p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-semibold">Request failed</strong>
                    <span>{serverError}</span>
                  </div>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate className="space-y-5">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Staff Email
                  </label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (emailError) setEmailError(validateEmail(e.target.value));
                      }}
                      className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all placeholder:text-slate-400"
                      placeholder="name@pharmacy.com"
                      disabled={isSubmitting}
                    />
                  </div>
                  {emailError && (
                    <p className="mt-1 text-xs text-rose-600 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      {emailError}
                    </p>
                  )}
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="w-full"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Sending…' : 'Send Reset Link'}
                </Button>
              </form>

              <div className="mt-5 text-center">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Sign In
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

