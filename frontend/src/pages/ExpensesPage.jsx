import React, { useCallback, useEffect, useState } from 'react';
import { DollarSign, Plus, Search, RefreshCw, Trash2, AlertCircle, Loader2 } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import {
  getExpenses,
  createExpense,
  deleteExpense,
} from '../services/api';
import { formatCurrency } from '../utilities/formatters';

const EXPENSE_CATEGORIES = [
  'Utilities & Power',
  'Store Rent',
  'Staff Salaries',
  'Logistics & Courier',
  'Equipment & Maintenance',
  'Software & Subscriptions',
  'Pharmacy Licensing & Legal',
  'Packaging & Stationery',
  'Other Operating Expenses',
];

const DEFAULT_FORM = {
  title: '',
  category: 'Utilities & Power',
  amount: '',
  expense_date: new Date().toISOString().split('T')[0],
  payment_method: 'cash',
  receipt_url: '',
  notes: '',
};

export function ExpensesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [expenses, setExpenses] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const loadExpenses = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getExpenses({
        search,
        category: categoryFilter,
        page,
        limit: 15,
      });
      setExpenses(res?.expenses || []);
      setTotal(res?.total ?? 0);
      setTotalPages(res?.total_pages ?? 1);
    } catch (err) {
      setError(err?.message || 'Failed to load expenses.');
    } finally {
      setIsLoading(false);
    }
  }, [search, categoryFilter, page]);

  useEffect(() => {
    loadExpenses();
  }, [loadExpenses]);

  const openAdd = () => {
    setForm(DEFAULT_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const submitExpense = async (e) => {
    e.preventDefault();
    if (!form.title?.trim() || !form.category || !form.amount) {
      setFormError('Title, Category, and Amount are required.');
      return;
    }
    const amt = parseFloat(form.amount) || 0;
    if (amt <= 0) {
      setFormError('Amount must be greater than zero.');
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      await createExpense({
        title: form.title.trim(),
        category: form.category,
        amount: amt,
        expense_date: form.expense_date,
        payment_method: form.payment_method,
        receipt_url: form.receipt_url?.trim() || null,
        notes: form.notes?.trim() || null,
      });
      setFormOpen(false);
      await loadExpenses();
    } catch (err) {
      setFormError(err?.message || 'Failed to record expense.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (exp) => {
    if (!window.confirm(`Are you sure you want to delete expense "${exp.title}"?`)) {
      return;
    }
    setDeletingId(exp.id);
    setError(null);
    try {
      await deleteExpense(exp.id);
      await loadExpenses();
    } catch (err) {
      setError(err?.message || 'Failed to delete expense.');
    } finally {
      setDeletingId(null);
    }
  };

  const totalExpenseSum = expenses.reduce((acc, it) => acc + (parseFloat(it.amount) || 0), 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Store Operating Expenses"
        subtitle="Track pharmacy utilities, shop maintenance, staff stipends, and overhead costs"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          <Button variant="primary" size="sm" icon={Plus} iconPosition="left" onClick={openAdd}>
            Record Expense
          </Button>
        }
      />

      {/* Overview Card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="text-xs text-slate-500 font-medium">Page Total Outflow</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">
            {formatCurrency(totalExpenseSum)}
          </div>
          <div className="text-xs text-slate-400 mt-1">Across current listings</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="text-xs text-slate-500 font-medium">Total Recorded Entries</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{total}</div>
          <div className="text-xs text-slate-400 mt-1">Operating expense items</div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
          <div className="text-xs text-slate-500 font-medium">Primary Cost Centers</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">Utilities &amp; Rent</div>
          <div className="text-xs text-slate-400 mt-1">Recurring monthly</div>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {/* Toolbar */}
          <div className="px-5 py-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search expenses by title or notes..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
            >
              <option value="">All Categories</option>
              {EXPENSE_CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>

            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={loadExpenses}
              disabled={isLoading}
            >
              Refresh
            </Button>
          </div>

          {error && (
            <div className="mx-5 my-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th className="py-3 px-5 font-semibold">Expense Title</th>
                  <th className="py-3 px-4 font-semibold">Category</th>
                  <th className="py-3 px-4 font-semibold">Date</th>
                  <th className="py-3 px-4 font-semibold text-right">Amount</th>
                  <th className="py-3 px-4 font-semibold">Payment Mode</th>
                  <th className="py-3 px-4 font-semibold">Logged By</th>
                  {isAdmin && <th className="py-3 px-5 font-semibold text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={isAdmin ? 7 : 6} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Loading operating expenses...
                    </td>
                  </tr>
                ) : expenses.length === 0 ? (
                  <tr>
                    <td colSpan={isAdmin ? 7 : 6} className="py-12 text-center text-slate-400">
                      <DollarSign className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      No expenses found for this filter.
                    </td>
                  </tr>
                ) : (
                  expenses.map((exp) => (
                    <tr key={exp.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-900">
                        {exp.title}
                        {exp.notes && (
                          <div className="text-xs text-slate-400 font-normal truncate max-w-xs">
                            {exp.notes}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <Badge variant="neutral" size="sm">
                          {exp.category}
                        </Badge>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600 whitespace-nowrap">
                        {exp.expense_date}
                      </td>
                      <td className="py-3.5 px-4 text-right font-semibold text-slate-900">
                        {formatCurrency(exp.amount)}
                      </td>
                      <td className="py-3.5 px-4 text-xs uppercase text-slate-600 font-medium">
                        {exp.payment_method}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {exp.created_by_name || 'Staff'}
                      </td>
                      {isAdmin && (
                        <td className="py-3.5 px-5 text-right">
                          <button
                            onClick={() => handleDelete(exp)}
                            disabled={deletingId === exp.id}
                            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                            title="Delete Expense"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>Page {page} of {totalPages} ({total} expenses)</div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Expense Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-base">Record Operating Expense</h3>
              <button onClick={() => setFormOpen(false)} className="text-slate-400 hover:text-slate-600 text-lg">
                &times;
              </button>
            </div>

            <form onSubmit={submitExpense} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Expense Title *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. October Electricity Bill, Store Sanitization"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Expense Category *
                  </label>
                  <select
                    value={form.category}
                    onChange={(e) => setForm({ ...form, category: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white"
                  >
                    {EXPENSE_CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Amount (₹) *
                  </label>
                  <input
                    type="number"
                    required
                    step="0.01"
                    min="0.01"
                    placeholder="1500.00"
                    value={form.amount}
                    onChange={(e) => setForm({ ...form, amount: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-semibold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Expense Date
                  </label>
                  <input
                    type="date"
                    required
                    value={form.expense_date}
                    onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Payment Method
                  </label>
                  <select
                    value={form.payment_method}
                    onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white uppercase font-medium"
                  >
                    <option value="cash">Cash</option>
                    <option value="upi">UPI / Online</option>
                    <option value="card">Card</option>
                    <option value="bank_transfer">Bank Transfer</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Notes / Voucher Details
                </label>
                <textarea
                  rows={2}
                  placeholder="Receipt voucher number, payee notes, remarks..."
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                />
              </div>

              <div className="pt-3 border-t border-slate-100 flex justify-end gap-3">
                <Button variant="outline" size="sm" type="button" onClick={() => setFormOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={saving}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5 inline" />
                  ) : null}
                  Record Expense
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
