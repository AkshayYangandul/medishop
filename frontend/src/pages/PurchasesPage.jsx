import React, { useCallback, useEffect, useState } from 'react';
import {
  ShoppingBag,
  Plus,
  Search,
  RefreshCw,
  Eye,
  Trash2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import {
  getPurchases,
  getPurchaseById,
  createPurchase,
  getSuppliers,
  getMedicines,
} from '../services/api';
import { formatCurrency } from '../utilities/formatters';

const DEFAULT_ITEM = {
  medicine_id: '',
  batch_no: '',
  mfg_date: '',
  expiry_date: '',
  quantity: 1,
  unit_cost: '',
  mrp: '',
  selling_price: '',
  tax_rate: 0,
};

export function PurchasesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [purchases, setPurchases] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [suppliers, setSuppliers] = useState([]);
  const [medicines, setMedicines] = useState([]);

  // Inward Purchase Form Modal
  const [formOpen, setFormOpen] = useState(false);
  const [supplierId, setSupplierId] = useState('');
  const [invoiceNo, setInvoiceNo] = useState('');
  const [purchaseDate, setPurchaseDate] = useState(new Date().toISOString().split('T')[0]);
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState([{ ...DEFAULT_ITEM }]);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);

  // Detail Modal
  const [selectedPurchase, setSelectedPurchase] = useState(null);

  const loadPurchases = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getPurchases({ search, page, limit: 15 });
      setPurchases(res?.purchases || []);
      setTotal(res?.total ?? 0);
      setTotalPages(res?.total_pages ?? 1);
    } catch (err) {
      setError(err?.message || 'Failed to load purchase orders.');
    } finally {
      setIsLoading(false);
    }
  }, [search, page]);

  useEffect(() => {
    loadPurchases();
  }, [loadPurchases]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [suppRes, medRes] = await Promise.all([
          getSuppliers(),
          getMedicines({ isActive: true, limit: 100 }),
        ]);
        if (cancelled) return;
        setSuppliers(suppRes || []);
        setMedicines(medRes?.medicines || []);
      } catch {
        // Degrades gracefully
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const openAddModal = () => {
    setSupplierId('');
    setInvoiceNo('');
    setPurchaseDate(new Date().toISOString().split('T')[0]);
    setNotes('');
    setItems([{ ...DEFAULT_ITEM }]);
    setFormError(null);
    setFormOpen(true);
  };

  const addItemRow = () => {
    setItems((prev) => [...prev, { ...DEFAULT_ITEM }]);
  };

  const removeItemRow = (idx) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateItemRow = (idx, field, val) => {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, [field]: val } : it))
    );
  };

  const submitPurchase = async (e) => {
    e.preventDefault();
    if (!supplierId) {
      setFormError('Please select a supplier.');
      return;
    }
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (!it.medicine_id || !it.batch_no?.trim() || !it.expiry_date) {
        setFormError(`Item #${i + 1}: Medicine, Batch No, and Expiry Date are required.`);
        return;
      }
      if (parseFloat(it.selling_price) > parseFloat(it.mrp)) {
        setFormError(`Item #${i + 1}: Selling price cannot exceed MRP.`);
        return;
      }
    }

    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        supplier_id: supplierId,
        invoice_no: invoiceNo?.trim() || undefined,
        purchase_date: purchaseDate,
        payment_status: 'paid',
        notes: notes?.trim() || null,
        items: items.map((it) => ({
          medicine_id: it.medicine_id,
          batch_no: it.batch_no.trim(),
          mfg_date: it.mfg_date || null,
          expiry_date: it.expiry_date,
          quantity: parseInt(it.quantity, 10) || 1,
          unit_cost: parseFloat(it.unit_cost) || 0,
          mrp: parseFloat(it.mrp) || parseFloat(it.unit_cost) || 0,
          selling_price: parseFloat(it.selling_price) || parseFloat(it.mrp) || 0,
          tax_rate: parseFloat(it.tax_rate) || 0,
        })),
      };

      await createPurchase(payload);
      setFormOpen(false);
      await loadPurchases();
    } catch (err) {
      setFormError(err?.message || 'Failed to record purchase bill.');
    } finally {
      setSaving(false);
    }
  };

  const viewPurchase = async (p) => {
    setSelectedPurchase(null);
    try {
      const detail = await getPurchaseById(p.id);
      setSelectedPurchase(detail);
    } catch (err) {
      alert(err?.message || 'Failed to fetch purchase details.');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Procurement & Supplier Inward Bills"
        subtitle="Record incoming stock batches, wholesale supplier receipts, and lot costs"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          isAdmin && (
            <Button variant="primary" size="sm" icon={Plus} iconPosition="left" onClick={openAddModal}>
              Record Inward Shipment
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
                placeholder="Search purchases by invoice number or vendor name..."
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={loadPurchases}
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
                  <th className="py-3 px-5 font-semibold">Vendor Bill #</th>
                  <th className="py-3 px-4 font-semibold">Bill Date</th>
                  <th className="py-3 px-4 font-semibold">Supplier</th>
                  <th className="py-3 px-4 font-semibold text-right">Net Amount</th>
                  <th className="py-3 px-4 font-semibold text-center">Payment</th>
                  <th className="py-3 px-4 font-semibold">Received By</th>
                  <th className="py-3 px-5 font-semibold text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Loading procurement bills...
                    </td>
                  </tr>
                ) : purchases.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <ShoppingBag className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      No purchase bills found.
                    </td>
                  </tr>
                ) : (
                  purchases.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-mono text-xs font-semibold text-slate-800">
                        {p.invoice_no}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {p.purchase_date}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-900">
                        {p.supplier_name || '—'}
                      </td>
                      <td className="py-3.5 px-4 text-right font-semibold text-slate-900">
                        {formatCurrency(p.net_amount)}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <Badge variant={p.payment_status === 'paid' ? 'success' : 'warning'} size="sm">
                          {p.payment_status}
                        </Badge>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        {p.received_by_name || 'Admin'}
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => viewPurchase(p)}
                          className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-md transition-colors"
                          title="View Inward Batches"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
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
              <div>Page {page} of {totalPages} ({total} bills)</div>
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

      {/* Record Purchase Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-base">
                Record Inward Supplier Purchase Bill
              </h3>
              <button onClick={() => setFormOpen(false)} className="text-slate-400 hover:text-slate-600 text-lg">
                &times;
              </button>
            </div>

            <form onSubmit={submitPurchase} className="flex-1 overflow-y-auto p-6 space-y-5">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Bill Header Info */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 bg-slate-50 p-4 rounded-xl">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Supplier *
                  </label>
                  <select
                    required
                    value={supplierId}
                    onChange={(e) => setSupplierId(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white"
                  >
                    <option value="">Select Supplier</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Vendor Invoice / Bill No
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. APEX/2026/892"
                    value={invoiceNo}
                    onChange={(e) => setInvoiceNo(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Purchase Date
                  </label>
                  <input
                    type="date"
                    required
                    value={purchaseDate}
                    onChange={(e) => setPurchaseDate(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                  />
                </div>
              </div>

              {/* Line Items List */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                    Inward Batches ({items.length} items)
                  </h4>
                  <Button variant="outline" size="sm" type="button" icon={Plus} onClick={addItemRow}>
                    Add Line Item
                  </Button>
                </div>

                <div className="space-y-3">
                  {items.map((it, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 border border-slate-200 rounded-xl space-y-3 relative bg-white"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-600">Item #{idx + 1}</span>
                        {items.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeItemRow(idx)}
                            className="text-slate-400 hover:text-rose-600 p-1"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Medicine *
                          </label>
                          <select
                            required
                            value={it.medicine_id}
                            onChange={(e) => updateItemRow(idx, 'medicine_id', e.target.value)}
                            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs bg-white"
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
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Batch No *
                          </label>
                          <input
                            type="text"
                            required
                            placeholder="e.g. BT-9021"
                            value={it.batch_no}
                            onChange={(e) => updateItemRow(idx, 'batch_no', e.target.value)}
                            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-mono"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                              Mfg Date
                            </label>
                            <input
                              type="date"
                              value={it.mfg_date}
                              onChange={(e) => updateItemRow(idx, 'mfg_date', e.target.value)}
                              className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs"
                            />
                          </div>
                          <div>
                            <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                              Expiry Date *
                            </label>
                            <input
                              type="date"
                              required
                              value={it.expiry_date}
                              onChange={(e) => updateItemRow(idx, 'expiry_date', e.target.value)}
                              className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Quantity *
                          </label>
                          <input
                            type="number"
                            required
                            min="1"
                            placeholder="100"
                            value={it.quantity}
                            onChange={(e) => updateItemRow(idx, 'quantity', e.target.value)}
                            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold"
                          />
                        </div>

                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Unit Cost (₹) *
                          </label>
                          <input
                            type="number"
                            required
                            step="0.01"
                            min="0"
                            placeholder="50.00"
                            value={it.unit_cost}
                            onChange={(e) => updateItemRow(idx, 'unit_cost', e.target.value)}
                            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold"
                          />
                        </div>

                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            MRP (₹) *
                          </label>
                          <input
                            type="number"
                            required
                            step="0.01"
                            min="0"
                            placeholder="80.00"
                            value={it.mrp}
                            onChange={(e) => updateItemRow(idx, 'mrp', e.target.value)}
                            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs"
                          />
                        </div>

                        <div>
                          <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                            Selling Price (₹) *
                          </label>
                          <input
                            type="number"
                            required
                            step="0.01"
                            min="0"
                            placeholder="75.00"
                            value={it.selling_price}
                            onChange={(e) => updateItemRow(idx, 'selling_price', e.target.value)}
                            className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-semibold text-brand-600"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Procurement Notes
                </label>
                <textarea
                  rows={2}
                  placeholder="Carrier reference, delivery challan number, batch condition..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
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
                  Record Shipment &amp; Inward Stock
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Purchase Detail Modal */}
      {selectedPurchase && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900 text-base">
                  Purchase Order {selectedPurchase.invoice_no}
                </h3>
                <p className="text-xs text-slate-400">
                  Date: {selectedPurchase.purchase_date} • Supplier: {selectedPurchase.supplier_name}
                </p>
              </div>
              <button
                onClick={() => setSelectedPurchase(null)}
                className="text-slate-400 hover:text-slate-600 text-lg"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="border border-slate-100 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                    <tr>
                      <th className="py-2.5 px-3">Medicine</th>
                      <th className="py-2.5 px-2">Batch</th>
                      <th className="py-2.5 px-2">Expiry</th>
                      <th className="py-2.5 px-2 text-center">Qty</th>
                      <th className="py-2.5 px-2 text-right">Unit Cost</th>
                      <th className="py-2.5 px-3 text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(selectedPurchase.items || []).map((it) => (
                      <tr key={it.id}>
                        <td className="py-2.5 px-3 font-medium text-slate-800">
                          {it.medicine_name}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-slate-600">{it.batch_no}</td>
                        <td className="py-2.5 px-2 text-slate-600">{it.expiry_date}</td>
                        <td className="py-2.5 px-2 text-center">{it.quantity}</td>
                        <td className="py-2.5 px-2 text-right">{formatCurrency(it.unit_cost)}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-slate-900">
                          {formatCurrency(it.subtotal)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end gap-6 text-sm font-semibold text-slate-900 pt-2">
                <span>Net Purchase Bill:</span>
                <span className="text-base text-brand-600">
                  {formatCurrency(selectedPurchase.net_amount)}
                </span>
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-100 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setSelectedPurchase(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
