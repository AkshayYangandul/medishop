import React, { useCallback, useEffect, useState } from 'react';
import { Truck, Plus, Search, RefreshCw, Pencil, Trash2, AlertCircle, Loader2 } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import {
  getSuppliers,
  createSupplier,
  updateSupplier,
  deleteSupplier,
} from '../services/api';

const DEFAULT_FORM = {
  name: '',
  contact_person: '',
  phone: '',
  email: '',
  address: '',
  gstin: '',
  drug_license_no: '',
  is_active: true,
};

export function SuppliersPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const loadSuppliers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getSuppliers({ search });
      setSuppliers(data || []);
    } catch (err) {
      setError(err?.message || 'Failed to load suppliers.');
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadSuppliers();
  }, [loadSuppliers]);

  const openAdd = () => {
    setEditingId(null);
    setForm(DEFAULT_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const openEdit = (supp) => {
    setEditingId(supp.id);
    setForm({
      name: supp.name ?? '',
      contact_person: supp.contact_person ?? '',
      phone: supp.phone ?? '',
      email: supp.email ?? '',
      address: supp.address ?? '',
      gstin: supp.gstin ?? '',
      drug_license_no: supp.drug_license_no ?? '',
      is_active: supp.is_active ?? true,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingId(null);
    setFormError(null);
  };

  const submitForm = async (e) => {
    e.preventDefault();
    if (!form.name?.trim() || !form.phone?.trim()) {
      setFormError('Supplier name and phone number are required.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: form.name.trim(),
        contact_person: form.contact_person?.trim() || null,
        phone: form.phone.trim(),
        email: form.email?.trim() || null,
        address: form.address?.trim() || null,
        gstin: form.gstin?.trim() || null,
        drug_license_no: form.drug_license_no?.trim() || null,
        is_active: !!form.is_active,
      };
      if (editingId) {
        await updateSupplier(editingId, payload);
      } else {
        await createSupplier(payload);
      }
      setFormOpen(false);
      await loadSuppliers();
    } catch (err) {
      setFormError(err?.message || 'Failed to save supplier.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (supp) => {
    if (!window.confirm(`Are you sure you want to delete supplier "${supp.name}"?`)) {
      return;
    }
    setDeletingId(supp.id);
    setError(null);
    try {
      await deleteSupplier(supp.id);
      await loadSuppliers();
    } catch (err) {
      setError(err?.message || 'Failed to delete supplier.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Wholesale Suppliers & Distributors"
        subtitle="Manage pharmaceutical vendors, GSTIN credentials, and drug licenses"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          isAdmin && (
            <Button variant="primary" size="sm" icon={Plus} iconPosition="left" onClick={openAdd}>
              Add Supplier
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
                placeholder="Search suppliers by name, phone, or GSTIN..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={loadSuppliers}
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
                  <th className="py-3 px-5 font-semibold">Vendor Name</th>
                  <th className="py-3 px-4 font-semibold">Contact Person</th>
                  <th className="py-3 px-4 font-semibold">Phone & Email</th>
                  <th className="py-3 px-4 font-semibold">GSTIN</th>
                  <th className="py-3 px-4 font-semibold">Drug License</th>
                  <th className="py-3 px-4 font-semibold text-center">Status</th>
                  {isAdmin && <th className="py-3 px-5 font-semibold text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={isAdmin ? 7 : 6} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Loading suppliers...
                    </td>
                  </tr>
                ) : suppliers.length === 0 ? (
                  <tr>
                    <td colSpan={isAdmin ? 7 : 6} className="py-12 text-center text-slate-400">
                      <Truck className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      No suppliers found.
                    </td>
                  </tr>
                ) : (
                  suppliers.map((supp) => (
                    <tr key={supp.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-900">
                        {supp.name}
                        {supp.address && (
                          <div className="text-xs text-slate-400 font-normal truncate max-w-xs">
                            {supp.address}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-700">{supp.contact_person || '—'}</td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-slate-800">{supp.phone}</div>
                        {supp.email && <div className="text-xs text-slate-400">{supp.email}</div>}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-slate-700">
                        {supp.gstin || '—'}
                      </td>
                      <td className="py-3.5 px-4 font-mono text-xs text-slate-700">
                        {supp.drug_license_no || '—'}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <Badge variant={supp.is_active ? 'success' : 'neutral'} size="sm">
                          {supp.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      {isAdmin && (
                        <td className="py-3.5 px-5 text-right space-x-2">
                          <button
                            onClick={() => openEdit(supp)}
                            className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-md transition-colors"
                            title="Edit Supplier"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(supp)}
                            disabled={deletingId === supp.id}
                            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                            title="Delete Supplier"
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
        </CardContent>
      </Card>

      {/* Add / Edit Supplier Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-base">
                {editingId ? 'Edit Supplier' : 'Add Supplier'}
              </h3>
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

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Vendor / Supplier Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Apollo Pharma Distributors"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Contact Person
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Ramesh Kumar"
                    value={form.contact_person}
                    onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Phone Number *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="+91 98765 43210"
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    GSTIN
                  </label>
                  <input
                    type="text"
                    placeholder="27AABCU9603R1ZM"
                    value={form.gstin}
                    onChange={(e) => setForm({ ...form, gstin: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Drug License No
                  </label>
                  <input
                    type="text"
                    placeholder="MH-MZ2-123456"
                    value={form.drug_license_no}
                    onChange={(e) => setForm({ ...form, drug_license_no: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  placeholder="orders@apollopharma.com"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Warehouse Address
                </label>
                <textarea
                  rows={2}
                  placeholder="Street, City, State, PIN..."
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-100 flex justify-end gap-3">
                <Button variant="outline" size="sm" type="button" onClick={closeForm}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={saving}>
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-1.5 inline" />
                  ) : null}
                  {editingId ? 'Save Changes' : 'Create Supplier'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
