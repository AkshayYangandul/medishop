import React, { useCallback, useEffect, useState } from 'react';
import {
  ShoppingCart,
  Search,
  Plus,
  Trash2,
  Receipt,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  Eye,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import {
  getMedicinesInventory,
  getCustomers,
  getInvoices,
  getInvoiceById,
  createInvoice,
} from '../services/api';
import { formatCurrency } from '../utilities/formatters';

export function SalesPage() {
  const [activeTab, setActiveTab] = useState('pos'); // 'pos' | 'history'

  // POS State
  const [inventory, setInventory] = useState([]);
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [medicineSearch, setMedicineSearch] = useState('');
  const [customers, setCustomers] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [prescriptionRef, setPrescriptionRef] = useState('');
  const [discountAmount, setDiscountAmount] = useState('');
  const [cart, setCart] = useState([]);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState(null);
  const [lastInvoice, setLastInvoice] = useState(null);

  // Invoices History State
  const [invoices, setInvoices] = useState([]);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [invoicesError, setInvoicesError] = useState(null);
  const [invoiceSearch, setInvoiceSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  // Load inventory for POS
  const loadInventory = useCallback(async () => {
    setInventoryLoading(true);
    try {
      const res = await getMedicinesInventory({ isActive: true, page: 1, limit: 100 });
      setInventory(res?.medicines || []);
    } catch {
      // Degrades gracefully
    } finally {
      setInventoryLoading(false);
    }
  }, []);

  // Load customers
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const custs = await getCustomers();
        if (!cancelled) setCustomers(custs || []);
      } catch {
        // Degrades gracefully
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (activeTab === 'pos') {
      loadInventory();
    }
  }, [activeTab, loadInventory]);

  // Load invoices history
  const loadInvoices = useCallback(async () => {
    setInvoicesLoading(true);
    setInvoicesError(null);
    try {
      const res = await getInvoices({ search: invoiceSearch, page, limit: 15 });
      setInvoices(res?.invoices || []);
      setTotalPages(res?.total_pages ?? 1);
    } catch (err) {
      setInvoicesError(err?.message || 'Failed to load past invoices.');
    } finally {
      setInvoicesLoading(false);
    }
  }, [invoiceSearch, page]);

  useEffect(() => {
    if (activeTab === 'history') {
      loadInvoices();
    }
  }, [activeTab, loadInvoices]);

  // POS Add to Cart
  const addToCart = (med, batch) => {
    if (!batch || batch.current_quantity <= 0) return;

    setCart((prev) => {
      const existingIdx = prev.findIndex((item) => item.batch_id === batch.id);
      if (existingIdx >= 0) {
        const updated = [...prev];
        const newQty = updated[existingIdx].quantity + 1;
        if (newQty <= batch.current_quantity) {
          updated[existingIdx].quantity = newQty;
        }
        return updated;
      }
      return [
        ...prev,
        {
          medicine_id: med.medicine_id,
          medicine_name: med.medicine_name,
          batch_id: batch.id,
          batch_no: batch.batch_no,
          available_qty: batch.current_quantity,
          unit_price: parseFloat(batch.selling_price) || 0,
          quantity: 1,
          discount_amount: 0,
          tax_rate: 0,
        },
      ];
    });
  };

  const updateCartQty = (batchId, nextQty) => {
    const qty = parseInt(nextQty, 10);
    setCart((prev) =>
      prev
        .map((item) => {
          if (item.batch_id === batchId) {
            const validQty = Math.max(1, Math.min(item.available_qty, isNaN(qty) ? 1 : qty));
            return { ...item, quantity: validQty };
          }
          return item;
        })
        .filter((item) => item.quantity > 0)
    );
  };

  const removeFromCart = (batchId) => {
    setCart((prev) => prev.filter((item) => item.batch_id !== batchId));
  };

  const subtotal = cart.reduce((acc, item) => acc + item.quantity * item.unit_price, 0);
  const discount = Math.min(subtotal, parseFloat(discountAmount) || 0);
  const grandTotal = Math.max(0, subtotal - discount);

  const handleCheckout = async () => {
    if (cart.length === 0) return;
    setCheckoutLoading(true);
    setCheckoutError(null);
    try {
      const payload = {
        customer_id: selectedCustomerId || null,
        payment_method: paymentMethod,
        payment_status: 'paid',
        discount_amount: discount,
        doctor_prescription_ref: prescriptionRef?.trim() || null,
        items: cart.map((item) => ({
          medicine_id: item.medicine_id,
          batch_id: item.batch_id,
          quantity: item.quantity,
          unit_price: item.unit_price,
          discount_amount: 0,
          tax_rate: 0,
        })),
      };

      const invoice = await createInvoice(payload);
      setLastInvoice(invoice);
      setCart([]);
      setDiscountAmount('');
      setPrescriptionRef('');
      setSelectedCustomerId('');
      await loadInventory();
    } catch (err) {
      setCheckoutError(err?.message || 'Checkout failed. Please check stock and try again.');
    } finally {
      setCheckoutLoading(false);
    }
  };

  const viewInvoiceDetail = async (inv) => {
    setSelectedInvoice(null);
    try {
      const detail = await getInvoiceById(inv.id);
      setSelectedInvoice(detail);
    } catch (err) {
      alert(err?.message || 'Failed to fetch invoice details.');
    }
  };

  const filteredMedicines = inventory.filter((m) =>
    m.medicine_name.toLowerCase().includes(medicineSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Counter Sales & Point-of-Sale (POS)"
        subtitle="Fast retail checkout, real-time inventory deduction, and billing history"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('pos')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'pos'
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              New Sale Counter
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                activeTab === 'history'
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-50'
              }`}
            >
              Sales Invoices History
            </button>
          </div>
        }
      />

      {/* POS TAB */}
      {activeTab === 'pos' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Medicine & Batch Catalog Selector */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <CardContent className="p-4 space-y-4">
                <div className="relative">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search medicines by name for quick billing..."
                    value={medicineSearch}
                    onChange={(e) => setMedicineSearch(e.target.value)}
                    className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                {inventoryLoading ? (
                  <div className="py-12 text-center text-slate-400">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                    Loading available pharmacy medicines...
                  </div>
                ) : filteredMedicines.length === 0 ? (
                  <div className="py-12 text-center text-slate-400 text-sm">
                    No matching medicines found in catalog.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 max-h-[500px] overflow-y-auto">
                    {filteredMedicines.map((med) => {
                      const availableBatches = (med.batches || []).filter(
                        (b) => b.current_quantity > 0
                      );
                      return (
                        <div key={med.medicine_id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div>
                            <div className="font-semibold text-slate-900 text-sm">
                              {med.medicine_name}
                            </div>
                            <div className="text-xs text-slate-500">
                              Stock: {med.current_stock} units • {availableBatches.length} active batches
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            {availableBatches.length === 0 ? (
                              <span className="text-xs text-rose-500 font-medium">Out of Stock</span>
                            ) : (
                              availableBatches.map((b) => (
                                <button
                                  key={b.id}
                                  onClick={() => addToCart(med, b)}
                                  className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 hover:border-brand-500 hover:bg-brand-50 transition-colors flex items-center gap-1.5 group"
                                  title={`Expiry: ${b.expiry_date}`}
                                >
                                  <span className="font-mono text-slate-700 group-hover:text-brand-700 font-medium">
                                    {b.batch_no}
                                  </span>
                                  <span className="text-slate-400 font-normal">
                                    ({b.current_quantity})
                                  </span>
                                  <span className="font-semibold text-emerald-600">
                                    {formatCurrency(b.selling_price)}
                                  </span>
                                  <Plus className="w-3.5 h-3.5 text-brand-600" />
                                </button>
                              ))
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Completed Invoice Success Banner */}
            {lastInvoice && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                <div className="flex-1 text-sm">
                  <div className="font-semibold text-emerald-900">
                    Invoice Billed Successfully: {lastInvoice.invoice_no}
                  </div>
                  <div className="text-emerald-700 text-xs mt-0.5">
                    Total: {formatCurrency(lastInvoice.net_amount)} • Method: {lastInvoice.payment_method.toUpperCase()} • Customer: {lastInvoice.customer_name || 'Walk-in'}
                  </div>
                </div>
                <Button variant="outline" size="sm" onClick={() => setLastInvoice(null)}>
                  Dismiss
                </Button>
              </div>
            )}
          </div>

          {/* Right Col: Bill / Cart Summary */}
          <div className="space-y-4">
            <Card>
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="font-semibold text-slate-900 text-base flex items-center gap-2">
                    <Receipt className="w-4 h-4 text-brand-600" />
                    Current Checkout Cart
                  </h3>
                  <Badge variant="brand" size="sm">
                    {cart.length} line items
                  </Badge>
                </div>

                {checkoutError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{checkoutError}</span>
                  </div>
                )}

                {/* Cart Items */}
                {cart.length === 0 ? (
                  <div className="py-10 text-center text-slate-400 text-sm">
                    <ShoppingCart className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                    Cart is empty. Click a batch from the medicines list to add.
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[280px] overflow-y-auto divide-y divide-slate-100">
                    {cart.map((item) => (
                      <div key={item.batch_id} className="pt-2 first:pt-0 flex items-center justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-slate-800 text-sm truncate">
                            {item.medicine_name}
                          </div>
                          <div className="text-xs text-slate-400 font-mono">
                            {item.batch_no} • {formatCurrency(item.unit_price)}/ea
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            type="number"
                            min="1"
                            max={item.available_qty}
                            value={item.quantity}
                            onChange={(e) => updateCartQty(item.batch_id, e.target.value)}
                            className="w-14 px-2 py-1 border border-slate-200 rounded text-center text-sm font-semibold"
                          />
                          <div className="font-semibold text-slate-900 text-sm w-16 text-right">
                            {formatCurrency(item.quantity * item.unit_price)}
                          </div>
                          <button
                            onClick={() => removeFromCart(item.batch_id)}
                            className="text-slate-400 hover:text-rose-600 p-1"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Customer, Payment, Prescription options */}
                <div className="space-y-3 pt-3 border-t border-slate-100">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Customer / Patient
                    </label>
                    <select
                      value={selectedCustomerId}
                      onChange={(e) => setSelectedCustomerId(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-sm bg-white"
                    >
                      <option value="">Walk-in Customer (Guest)</option>
                      {customers.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} {c.phone ? `(${c.phone})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Payment Mode
                      </label>
                      <select
                        value={paymentMethod}
                        onChange={(e) => setPaymentMethod(e.target.value)}
                        className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-sm bg-white uppercase font-medium"
                      >
                        <option value="cash">Cash</option>
                        <option value="upi">UPI / QR</option>
                        <option value="card">Card</option>
                        <option value="credit">Store Credit</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-700 mb-1">
                        Discount (₹)
                      </label>
                      <input
                        type="number"
                        min="0"
                        placeholder="0.00"
                        value={discountAmount}
                        onChange={(e) => setDiscountAmount(e.target.value)}
                        className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Doctor Prescription Ref (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Rx #1092 / Dr. Sen"
                      value={prescriptionRef}
                      onChange={(e) => setPrescriptionRef(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-200 rounded-lg text-sm"
                    />
                  </div>
                </div>

                {/* Calculation breakdown */}
                <div className="space-y-1.5 pt-3 border-t border-slate-100 text-sm">
                  <div className="flex justify-between text-slate-500">
                    <span>Subtotal:</span>
                    <span>{formatCurrency(subtotal)}</span>
                  </div>
                  {discount > 0 && (
                    <div className="flex justify-between text-rose-600">
                      <span>Discount:</span>
                      <span>-{formatCurrency(discount)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-base font-bold text-slate-900 pt-1">
                    <span>Grand Total:</span>
                    <span>{formatCurrency(grandTotal)}</span>
                  </div>
                </div>

                <Button
                  variant="primary"
                  size="md"
                  className="w-full justify-center py-2.5 font-semibold"
                  disabled={cart.length === 0 || checkoutLoading}
                  onClick={handleCheckout}
                >
                  {checkoutLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2 inline" />
                  ) : null}
                  Complete Sale &amp; Issue Receipt
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* HISTORY TAB */}
      {activeTab === 'history' && (
        <Card>
          <CardContent className="p-0">
            {/* Toolbar */}
            <div className="px-5 py-4 border-b border-slate-100 flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search invoices by invoice number or customer name..."
                  value={invoiceSearch}
                  onChange={(e) => {
                    setInvoiceSearch(e.target.value);
                    setPage(1);
                  }}
                  className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                icon={RefreshCw}
                onClick={loadInvoices}
                disabled={invoicesLoading}
              >
                Refresh
              </Button>
            </div>

            {invoicesError && (
              <div className="mx-5 my-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{invoicesError}</span>
              </div>
            )}

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-5 font-semibold">Invoice #</th>
                    <th className="py-3 px-4 font-semibold">Date &amp; Time</th>
                    <th className="py-3 px-4 font-semibold">Customer</th>
                    <th className="py-3 px-4 font-semibold">Payment</th>
                    <th className="py-3 px-4 font-semibold text-right">Amount</th>
                    <th className="py-3 px-4 font-semibold text-center">Status</th>
                    <th className="py-3 px-5 font-semibold text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {invoicesLoading ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-400">
                        <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                        Loading past invoices...
                      </td>
                    </tr>
                  ) : invoices.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-slate-400">
                        <Receipt className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                        No past sales invoices found.
                      </td>
                    </tr>
                  ) : (
                    invoices.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="py-3.5 px-5 font-mono text-xs font-semibold text-slate-800">
                          {inv.invoice_no}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-600 whitespace-nowrap">
                          {inv.created_at ? new Date(inv.created_at).toLocaleString() : '—'}
                        </td>
                        <td className="py-3.5 px-4 text-slate-800 font-medium">
                          {inv.customer_name || 'Walk-in Customer'}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-100 font-medium text-slate-700 uppercase">
                            {inv.payment_method}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right font-semibold text-slate-900">
                          {formatCurrency(inv.net_amount)}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <Badge variant={inv.payment_status === 'paid' ? 'success' : 'warning'} size="sm">
                            {inv.payment_status}
                          </Badge>
                        </td>
                        <td className="py-3.5 px-5 text-right">
                          <button
                            onClick={() => viewInvoiceDetail(inv)}
                            className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-md transition-colors"
                            title="View Items"
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
                <div>Page {page} of {totalPages}</div>
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
      )}

      {/* Invoice Detail Modal */}
      {selectedInvoice && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-slate-900 text-base">
                  Invoice {selectedInvoice.invoice_no}
                </h3>
                <p className="text-xs text-slate-400">
                  {new Date(selectedInvoice.created_at).toLocaleString()} • Cashier: {selectedInvoice.cashier_name || 'Counter'}
                </p>
              </div>
              <button
                onClick={() => setSelectedInvoice(null)}
                className="text-slate-400 hover:text-slate-600 text-lg"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-xs bg-slate-50 p-3 rounded-lg">
                <div>
                  <span className="text-slate-500">Customer:</span>{' '}
                  <span className="font-semibold text-slate-800">
                    {selectedInvoice.customer_name || 'Walk-in'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Payment:</span>{' '}
                  <span className="font-semibold text-slate-800 uppercase">
                    {selectedInvoice.payment_method} ({selectedInvoice.payment_status})
                  </span>
                </div>
                {selectedInvoice.doctor_prescription_ref && (
                  <div className="col-span-2">
                    <span className="text-slate-500">Doctor / Rx:</span>{' '}
                    <span className="font-semibold text-slate-800">
                      {selectedInvoice.doctor_prescription_ref}
                    </span>
                  </div>
                )}
              </div>

              {/* Items Table */}
              <div className="border border-slate-100 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                    <tr>
                      <th className="py-2.5 px-3">Medicine</th>
                      <th className="py-2.5 px-2">Batch</th>
                      <th className="py-2.5 px-2 text-center">Qty</th>
                      <th className="py-2.5 px-2 text-right">Price</th>
                      <th className="py-2.5 px-3 text-right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(selectedInvoice.items || []).map((it) => (
                      <tr key={it.id}>
                        <td className="py-2.5 px-3 font-medium text-slate-800">
                          {it.medicine_name}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-slate-600">{it.batch_no}</td>
                        <td className="py-2.5 px-2 text-center">{it.quantity}</td>
                        <td className="py-2.5 px-2 text-right">{formatCurrency(it.unit_price)}</td>
                        <td className="py-2.5 px-3 text-right font-semibold text-slate-900">
                          {formatCurrency(it.subtotal)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end gap-6 text-sm font-semibold text-slate-900 pt-2">
                <span>Net Total Billed:</span>
                <span className="text-base text-brand-600">
                  {formatCurrency(selectedInvoice.net_amount)}
                </span>
              </div>
            </div>

            <div className="px-6 py-3 border-t border-slate-100 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setSelectedInvoice(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
