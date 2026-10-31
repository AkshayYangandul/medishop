import React, { useCallback, useEffect, useState } from 'react';
import { Award, Plus, Search, RefreshCw, Pencil, Trash2, AlertCircle, Loader2 } from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useAuth } from '../context/AuthContext';
import {
  getMedicineBrands,
  createBrand,
  updateBrand,
  deleteBrand,
} from '../services/api';

const DEFAULT_FORM = {
  name: '',
  manufacturer: '',
  contact_email: '',
  contact_phone: '',
};

export function BrandsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [brands, setBrands] = useState([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const loadBrands = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getMedicineBrands();
      setBrands(data || []);
    } catch (err) {
      setError(err?.message || 'Failed to load brands. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBrands();
  }, [loadBrands]);

  const openAdd = () => {
    setEditingId(null);
    setForm(DEFAULT_FORM);
    setFormError(null);
    setFormOpen(true);
  };

  const openEdit = (brand) => {
    setEditingId(brand.id);
    setForm({
      name: brand.name ?? '',
      manufacturer: brand.manufacturer ?? '',
      contact_email: brand.contact_email ?? '',
      contact_phone: brand.contact_phone ?? '',
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
    if (!form.name?.trim()) {
      setFormError('Brand name is required.');
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const payload = {
        name: form.name.trim(),
        manufacturer: form.manufacturer?.trim() || null,
        contact_email: form.contact_email?.trim() || null,
        contact_phone: form.contact_phone?.trim() || null,
      };
      if (editingId) {
        await updateBrand(editingId, payload);
      } else {
        await createBrand(payload);
      }
      setFormOpen(false);
      await loadBrands();
    } catch (err) {
      setFormError(err?.message || 'Failed to save brand.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (brand) => {
    if (!window.confirm(`Are you sure you want to delete brand "${brand.name}"?`)) {
      return;
    }
    setDeletingId(brand.id);
    setError(null);
    try {
      await deleteBrand(brand.id);
      await loadBrands();
    } catch (err) {
      setError(err?.message || 'Failed to delete brand.');
    } finally {
      setDeletingId(null);
    }
  };

  const filteredBrands = brands.filter((b) =>
    b.name.toLowerCase().includes(search.toLowerCase()) ||
    (b.manufacturer && b.manufacturer.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Medicine Brands & Manufacturers"
        subtitle="Pharmaceutical companies and manufacturing brand directory"
        badge={
          <Badge variant="brand" size="md" dot>
            Live Data
          </Badge>
        }
        actions={
          isAdmin && (
            <Button variant="primary" size="sm" icon={Plus} iconPosition="left" onClick={openAdd}>
              Add Brand
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
                placeholder="Search brands by brand name or manufacturer..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              onClick={loadBrands}
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
                  <th className="py-3 px-5 font-semibold">Brand Name</th>
                  <th className="py-3 px-4 font-semibold">Manufacturer</th>
                  <th className="py-3 px-4 font-semibold">Contact Email</th>
                  <th className="py-3 px-4 font-semibold">Contact Phone</th>
                  {isAdmin && <th className="py-3 px-5 font-semibold text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={isAdmin ? 5 : 4} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Loading brands...
                    </td>
                  </tr>
                ) : filteredBrands.length === 0 ? (
                  <tr>
                    <td colSpan={isAdmin ? 5 : 4} className="py-12 text-center text-slate-400">
                      <Award className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      No medicine brands found.
                    </td>
                  </tr>
                ) : (
                  filteredBrands.map((brand) => (
                    <tr key={brand.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3.5 px-5 font-medium text-slate-900">{brand.name}</td>
                      <td className="py-3.5 px-4 text-slate-700">{brand.manufacturer || '—'}</td>
                      <td className="py-3.5 px-4 text-slate-600 font-mono text-xs">
                        {brand.contact_email || '—'}
                      </td>
                      <td className="py-3.5 px-4 text-slate-600 text-xs">
                        {brand.contact_phone || '—'}
                      </td>
                      {isAdmin && (
                        <td className="py-3.5 px-5 text-right space-x-2">
                          <button
                            onClick={() => openEdit(brand)}
                            className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-md transition-colors"
                            title="Edit Brand"
                          >
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(brand)}
                            disabled={deletingId === brand.id}
                            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                            title="Delete Brand"
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

      {/* Add / Edit Brand Modal */}
      {formOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden animate-scale-in">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-base">
                {editingId ? 'Edit Medicine Brand' : 'Add Medicine Brand'}
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
                  Brand Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Cipla, Sun Pharma, GlaxoSmithKline"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Manufacturer Company
                </label>
                <input
                  type="text"
                  placeholder="e.g. Cipla Ltd."
                  value={form.manufacturer}
                  onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Contact Email
                  </label>
                  <input
                    type="email"
                    placeholder="contact@manufacturer.com"
                    value={form.contact_email}
                    onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    placeholder="+91 98765 43210"
                    value={form.contact_phone}
                    onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
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
                  {editingId ? 'Save Changes' : 'Create Brand'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
