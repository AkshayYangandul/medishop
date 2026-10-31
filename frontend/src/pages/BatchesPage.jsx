import React, { useCallback, useEffect, useState } from 'react';
import { Layers, Plus, Search, RefreshCw, AlertCircle, Loader2 } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import {
  getBatches,
  createBatch,
  getMedicines,
  getSuppliers,
} from '../services/api';
import { formatCurrency } from '../utilities/formatters';

const DEFAULT_FORM = {
  medicine_id: '',
  supplier_id: '',
  batch_no: '',
  mfg_date: '',
  expiry_date: '',
  purchase_cost: '',
  mrp: '',
  selling_price: '',
  initial_quantity: '',
};

export function BatchesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [batches, setBatches] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [medicines, setMedicines] = useState([]);
  const [suppliers, setSuppliers] = useState([]);

  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);

  const loadBatches = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getBatches({
        search,
        statusFilter,
        page,
        limit,
      });
      setBatches(data?.batches || []);
      setTotal(data?.total ?? 0);
      setTotalPages(data?.total_pages ?? 1);
    } catch (err) {
      setError(err?.message || 'Failed to load batches.');
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter, page, limit]);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [medRes, suppRes] = await Promise.all([
          getMedicines({ isActive: true, limit: 100 }),
          getSuppliers(),
        ]);
        if (cancelled) return;
        setMedicines(medRes?.medicines || []);
        setSuppliers(suppRes || []);
      } catch {
        // Lookups degrade gracefully
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const openAdd = () => {
    setForm(DEFAULT_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setFormError(null);
  };

  const submitForm = async (e) => {
    e.preventDefault();
    if (!form.medicine_id || !form.batch_no?.trim() || !form.expiry_date) {
      setFormError('Medicine, Batch number, and Expiry date are required.');
      return;
    }
    const cost = parseFloat(form.purchase_cost) || 0;
    const mrp = parseFloat(form.mrp) || 0;
    const price = parseFloat(form.selling_price) || 0;
    const qty = parseInt(form.initial_quantity, 10) || 0;

    if (price > mrp) {
      setFormError('Selling price cannot exceed MRP.');
      return;
    }
    if (form.mfg_date && form.expiry_date && form.mfg_date >= form.expiry_date) {
      setFormError('Manufacturing date must be earlier than expiry date.');
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      await createBatch({
        medicine_id: form.medicine_id,
        supplier_id: form.supplier_id || null,
        batch_no: form.batch_no.trim(),
        mfg_date: form.mfg_date || null,
        expiry_date: form.expiry_date,
        purchase_cost: cost,
        mrp: mrp,
        selling_price: price,
        initial_quantity: qty,
      });
      setFormOpen(false);
      await loadBatches();
    } catch (err) {
      setFormError(err?.message || 'Failed to create batch.');
    } finally {
      setSaving(false);
    }
  };

  const getExpiryBadge = (expiryDate) => {
    if (!expiryDate) return null;
    const today = new Date();
    const exp = new Date(expiryDate);
    const diffDays = Math.ceil((exp - today) / (1000 * 60 * 60 * 24));

    if (diffDays < 0) {
      return <Badge variant="danger" size="sm">Expired</Badge>;
    }
    if (diffDays <= 60) {
      return <Badge variant="warning" size="sm">Expiring ({diffDays}d)</Badge>;
    }
    return <Badge variant="success" size="sm">{diffDays} days left</Badge>;
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medicine Batches & Stock Intake"
        subtitle="Lot tracking, expiration management, and unit cost records"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          isAdmin && (
            <Button variant="primary" size="sm" icon={Plus} iconPosition="left" onClick={openAdd}>
              Add Batch Intake
            </Button>
          )
        }
      />

      <Card>
        <CardContent className="p-0">
          {/* Toolbar */}
          <div className="px-5 py-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search batches by batch number or medicine name..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
            >
              <option value="">All Statuses</option>
              <option value="expiring_soon">Expiring Soon (90 Days)</option>
              <option value="expired">Expired Batches</option>
              <option value="low_stock">Low Stock (≤ 10)</option>
              <option value="in_stock">In Stock (&gt; 0)</option>
            </select>

            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={loadBatches}
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
                  <th className="py-3 px-5 font-semibold">Medicine</th>
                  <th className="py-3 px-4 font-semibold">Batch No</th>
                  <th className="py-3 px-4 font-semibold">Expiry Date</th>
                  <th className="py-3 px-4 font-semibold">Stock Qty</th>
                  <th className="py-3 px-4 font-semibold text-right">Cost</th>
                  <th className="py-3 px-4 font-semibold text-right">MRP</th>
                  <th className="py-3 px-4 font-semibold text-right">Selling Price</th>
                  <th className="py-3 px-5 font-semibold">Supplier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Loading batches...
                    </td>
                  </tr>
                ) : batches.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-400">
                      <Layers className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      No batches found.
                    </td>
                  </tr>
                ) : (
                  batches.map((b) => (
                    <tr key={b.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-900">
                        {b.medicine_name || '—'}
                        <div className="text-xs text-slate-400 font-normal">
                          {b.dosage_form} • {b.unit}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs font-semibold text-slate-800">
                        {b.batch_no}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-700">{b.expiry_date}</span>
                          {getExpiryBadge(b.expiry_date)}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`font-semibold ${b.current_quantity <= 10 ? 'text-rose-600' : 'text-slate-800'}`}>
                          {b.current_quantity}
                        </span>
                        <span className="text-slate-400 text-xs ml-1">/ {b.initial_quantity}</span>
                      </td>
                      <td className="py-3.5 px-4 text-right text-slate-600 text-xs">
                        {formatCurrency(b.purchase_cost)}
                      </td>
                      <td className="py-3.5 px-4 text-right text-slate-600 text-xs">
                        {formatCurrency(b.mrp)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-medium text-slate-900">
                        {formatCurrency(b.selling_price)}
                      </td>
                      <td className="py-3.5 px-5 text-slate-600 text-xs">
                        {b.supplier_name || '—'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-5 py-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>
                Showing page {page} of {totalPages} ({total} batches)
              </div>
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

      {/* Add Batch Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-xl w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-base">Record Inward Batch</h3>
              <button onClick={closeForm} className="text-slate-400 hover:text-slate-600 text-lg">
                &times;
              </button>
            </div>

            <form onSubmit={submitForm} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Medicine *
                  </label>
                  <select
                    required
                    value={form.medicine_id}
                    onChange={(e) => setForm({ ...form, medicine_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                  >
                    <option value="">Select Medicine</option>
                    {medicines.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.dosage_form})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Supplier (Optional)
                  </label>
                  <select
                    value={form.supplier_id}
                    onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
                  >
                    <option value="">Select Supplier</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Batch Number *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. B-9021A"
                    value={form.batch_no}
                    onChange={(e) => setForm({ ...form, batch_no: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Mfg Date
                  </label>
                  <input
                    type="date"
                    value={form.mfg_date}
                    onChange={(e) => setForm({ ...form, mfg_date: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Expiry Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={form.expiry_date}
                    onChange={(e) => setForm({ ...form, expiry_date: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Quantity Received *
                  </label>
                  <input
                    type="number"
                    required
                    min="1"
                    placeholder="100"
                    value={form.initial_quantity}
                    onChange={(e) => setForm({ ...form, initial_quantity: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Purchase Cost (₹)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="45.00"
                    value={form.purchase_cost}
                    onChange={(e) => setForm({ ...form, purchase_cost: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    MRP (₹) *
                  </label>
                  <input
                    type="number"
                    required
                    step="0.01"
                    min="0"
                    placeholder="65.00"
                    value={form.mrp}
                    onChange={(e) => setForm({ ...form, mrp: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Selling Price (₹) *
                  </label>
                  <input
                    type="number"
                    required
                    step="0.01"
                    min="0"
                    placeholder="60.00"
                    value={form.selling_price}
                    onChange={(e) => setForm({ ...form, selling_price: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex justify-end gap-3">
                <Button variant="outline" size="sm" type="button" onClick={closeForm}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={saving}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5 inline" />
                  ) : null}
                  Save Batch
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
