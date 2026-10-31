import React, { useCallback, useEffect, useState } from 'react';
import { Pill, Plus, Search, RefreshCw, Pencil, Trash2, AlertCircle, Loader2 } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import { getMedicines, createMedicine, updateMedicine, getMedicineCategories, getMedicineBrands } from '../services/api';

const DEFAULT_FORM = {
  name: '',
  genericName: '',
  categoryId: '',
  brandId: '',
  dosageForm: 'Tablet',
  strength: '',
  unit: 'Strip',
  hsnCode: '',
  requiresPrescription: false,
  minStockAlert: 10,
};

const DOSAGE_FORMS = [
  'Tablet',
  'Capsule',
  'Syrup',
  'Injection',
  'Ointment',
  'Drops',
  'Inhaler',
  'Other',
];

export function MedicinesPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [medicines, setMedicines] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [totalPages, setTotalPages] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);

  const loadMedicines = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const isActiveParam = statusFilter === 'all' ? undefined : statusFilter === 'active';
      const response = await getMedicines({ search, categoryId, isActive: isActiveParam, page, limit });
      setMedicines(response?.medicines || []);
      setTotal(response?.total ?? 0);
      setTotalPages(response?.total_pages ?? 1);
    } catch (err) {
      setError(err?.message || 'Failed to load medicines. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, [search, categoryId, statusFilter, page, limit]);

  useEffect(() => {
    loadMedicines();
  }, [loadMedicines]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cats, brandList] = await Promise.all([getMedicineCategories(), getMedicineBrands()]);
        if (cancelled) return;
        setCategories(cats || []);
        setBrands(brandList || []);
      } catch {
        // Filters degrade to empty lists if lookups fail; catalogue list error is surfaced separately.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const applySearch = () => {
    setSearch(searchInput.trim());
    setPage(1);
  };

  const openAdd = () => {
    setEditingId(null);
    setForm(DEFAULT_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const openEdit = (medicine) => {
    setEditingId(medicine.id);
    setForm({
      name: medicine.name ?? '',
      genericName: medicine.generic_name ?? '',
      categoryId: medicine.category_id ?? '',
      brandId: medicine.brand_id ?? '',
      dosageForm: medicine.dosage_form ?? 'Tablet',
      strength: medicine.strength ?? '',
      unit: medicine.unit ?? 'Strip',
      hsnCode: medicine.hsn_code ?? '',
      requiresPrescription: !!medicine.requires_prescription,
      minStockAlert: medicine.min_stock_alert ?? 10,
    });
    setFormError(null);
    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingId(null);
    setFormError(null);
  };

  const submitForm = async (event) => {
    event.preventDefault();
    if (!form.name?.trim() || !form.categoryId || !form.dosageForm) {
      setFormError('Medicine name, category and dosage form are required.');
      return;
    }
    setSaving(true);
    setFormError(null);
    const payload = {
      name: form.name.trim(),
      generic_name: form.genericName?.trim() || null,
      category_id: form.categoryId,
      brand_id: form.brandId || null,
      dosage_form: form.dosageForm,
      strength: form.strength?.trim() || null,
      unit: form.unit,
      hsn_code: form.hsnCode?.trim() || null,
      requires_prescription: !!form.requiresPrescription,
      min_stock_alert: Number(form.minStockAlert) || 0,
    };
    try {
      if (editingId) {
        await updateMedicine(editingId, payload);
      } else {
        await createMedicine(payload);
      }
      setFormOpen(false);
      await loadMedicines();
    } catch (err) {
      setFormError(err?.message || 'Failed to save the medicine. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (medicine) => {
    const nextActive = !medicine.is_active;
    try {
      await updateMedicine(medicine.id, { is_active: nextActive });
      await loadMedicines();
    } catch (err) {
      setError(err?.message || 'Failed to update the medicine status.');
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medicines Catalog"
        subtitle="Master directory of pharmaceutical drugs, dosage formulations, and pricing"
        badge={
          <Badge variant="brand" size="md" dot>
            Phase 2 • Live Data
          </Badge>
        }
        actions={
          isAdmin && (
            <Button variant="primary" size="sm" icon={Plus} iconPosition="left" onClick={openAdd}>
              Add Medicine
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
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') applySearch();
                }}
                placeholder="Search medicines by name or generic name..."
                className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all"
              />
            </div>
            <select
              value={categoryId}
              onChange={(e) => {
                setCategoryId(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none bg-white"
            >
              <option value="active">Active catalogue</option>
              <option value="inactive">Deactivated</option>
              <option value="all">All statuses</option>
            </select>
            <Button variant="outline" size="sm" icon={Search} onClick={applySearch}>
              Search
            </Button>
            <Button variant="outline" size="sm" icon={RefreshCw} onClick={loadMedicines}>
              Refresh
            </Button>
          </div>

          {/* States */}
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin text-brand-600" />
              <p className="text-sm">Loading medicines...</p>
            </div>
          ) : error ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 px-6 text-center">
              <AlertCircle className="w-8 h-8 text-rose-500" />
              <p className="text-sm font-medium text-slate-700">Failed to load medicines</p>
              <p className="text-xs text-slate-500 max-w-md">{error}</p>
              <Button variant="outline" size="sm" icon={RefreshCw} onClick={loadMedicines}>
                Retry
              </Button>
            </div>
          ) : medicines.length === 0 ? (
            <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-500">
              <Pill className="w-10 h-10 text-slate-300" />
              <p className="text-sm font-medium text-slate-700">No medicines found</p>
              <p className="text-xs text-slate-500">
                {search || categoryId
                  ? 'No medicines match the current search/filters.'
                  : 'No medicines have been added yet. Add one to build the catalogue.'}
              </p>
              {isAdmin && !search && !categoryId && (
                <Button variant="primary" size="sm" icon={Plus} onClick={openAdd}>
                  Add Medicine
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Medicine</th>
                    <th className="px-5 py-3 font-semibold">Category</th>
                    <th className="px-5 py-3 font-semibold">Brand</th>
                    <th className="px-5 py-3 font-semibold">Dosage</th>
                    <th className="px-5 py-3 font-semibold">Unit</th>
                    <th className="px-5 py-3 font-semibold">Stock</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    {isAdmin && <th className="px-5 py-3 font-semibold text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {medicines.map((med) => {
                    const stock = Number(med.current_stock ?? 0);
                    const isLow = stock < Number(med.min_stock_alert ?? 0);
                    return (
                      <tr key={med.id} className="hover:bg-slate-50/60">
                        <td className="px-5 py-3.5">
                          <div className="font-semibold text-slate-800">{med.name}</div>
                          {med.generic_name && (
                            <div className="text-xs text-slate-500">{med.generic_name}</div>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-slate-600">{med.category_name || '—'}</td>
                        <td className="px-5 py-3.5 text-slate-600">{med.brand_name || '—'}</td>
                        <td className="px-5 py-3.5 text-slate-600">
                          {med.dosage_form}
                          {med.strength ? ` • ${med.strength}` : ''}
                        </td>
                        <td className="px-5 py-3.5 text-slate-600">{med.unit || 'Strip'}</td>
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-700">{stock}</span>
                            {isLow && (
                              <Badge variant="warning" size="sm">
                                Low
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-3.5">
                          <Badge variant={med.is_active ? 'success' : 'neutral'} size="sm" dot>
                            {med.is_active ? 'Active' : 'Inactive'}
                          </Badge>
                        </td>
                        {isAdmin && (
                          <td className="px-5 py-3.5 text-right">
                            <div className="inline-flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                icon={Pencil}
                                iconPosition="left"
                                onClick={() => openEdit(med)}
                              >
                                Edit
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                icon={Trash2}
                                iconPosition="left"
                                onClick={() => toggleActive(med)}
                                title={med.is_active ? 'Deactivate medicine' : 'Reactivate medicine'}
                              >
                                {med.is_active ? 'Deactivate' : 'Activate'}
                              </Button>
                            </div>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-slate-600">
          <span>Showing {medicines.length} of {total} medicines</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Previous
            </Button>
            <span className="text-xs font-medium">
              Page {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Add / Edit Medicine Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4">
          <div className="bg-white rounded-2xl shadow-soft-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-bold text-slate-800 text-lg">{editingId ? 'Edit Medicine' : 'Add Medicine'}</h3>
              <Button variant="ghost" size="sm" onClick={closeForm}>
                Close
              </Button>
            </div>
            <form onSubmit={submitForm} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <span>{formError}</span>
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Medicine Name *
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Generic Name
                  </label>
                  <input
                    type="text"
                    value={form.genericName}
                    onChange={(e) => setForm({ ...form, genericName: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Strength
                  </label>
                  <input
                    type="text"
                    value={form.strength}
                    onChange={(e) => setForm({ ...form, strength: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Category *
                  </label>
                  <select
                    value={form.categoryId}
                    onChange={(e) => setForm({ ...form, categoryId: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  >
                    <option value="">Select category...</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Brand
                  </label>
                  <select
                    value={form.brandId}
                    onChange={(e) => setForm({ ...form, brandId: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  >
                    <option value="">Select brand (optional)...</option>
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Dosage Form *
                  </label>
                  <select
                    value={form.dosageForm}
                    onChange={(e) => setForm({ ...form, dosageForm: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  >
                    {DOSAGE_FORMS.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Unit
                  </label>
                  <input
                    type="text"
                    value={form.unit}
                    onChange={(e) => setForm({ ...form, unit: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    HSN Code
                  </label>
                  <input
                    type="text"
                    value={form.hsnCode}
                    onChange={(e) => setForm({ ...form, hsnCode: e.target.value })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Min Stock Alert
                  </label>
                  <input
                    type="number"
                    min={0}
                    value={form.minStockAlert}
                    onChange={(e) => setForm({ ...form, minStockAlert: Number(e.target.value) || 0 })}
                    className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.requiresPrescription}
                  onChange={(e) => setForm({ ...form, requiresPrescription: e.target.checked })}
                  className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                Requires prescription
              </label>
              <div className="flex justify-end gap-3 pt-2">
                <Button type="button" variant="outline" size="sm" onClick={closeForm}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="sm" disabled={saving}>
                  {saving ? 'Saving...' : editingId ? 'Update Medicine' : 'Create Medicine'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
