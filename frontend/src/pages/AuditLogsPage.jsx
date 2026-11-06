import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Clock,
  Eye,
  FileText,
  Filter,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
  X,
} from 'lucide-react';
import { PageHeader } from '../components/common/PageHeader';
import { Badge } from '../components/common/Badge';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useDocumentTitle } from '../hooks/useDocumentTitle';
import { getAuditLogs, getAuditLogById, getAuditLogOptions } from '../services/api';

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const FALLBACK_MODULES = [
  'auth',
  'users',
  'inventory',
  'catalogue',
  'procurement',
  'sales',
  'finance',
  'system',
];

const FALLBACK_ACTIONS = [
  'LOGIN_SUCCESS',
  'LOGIN_FAILED',
  'ACCOUNT_LOCKED',
  'ACCOUNT_UNLOCK',
  'PASSWORD_RESET_SUCCESS',
  'USER_CREATED',
  'ROLE_OR_STATUS_CHANGE',
  'ACCOUNT_DELETE',
  'INITIAL_ADMIN_PROVISIONING',
  'MEDICINE_CREATED',
  'MEDICINE_UPDATED',
  'MEDICINE_DEACTIVATED',
  'BATCH_CREATED',
  'CATEGORY_CREATED',
  'CATEGORY_UPDATED',
  'CATEGORY_DELETED',
  'BRAND_CREATED',
  'BRAND_UPDATED',
  'BRAND_DELETED',
  'SUPPLIER_CREATED',
  'SUPPLIER_UPDATED',
  'SUPPLIER_DELETED',
  'PURCHASE_CREATED',
  'CUSTOMER_CREATED',
  'CUSTOMER_UPDATED',
  'CUSTOMER_DELETED',
  'INVOICE_CREATED',
  'EXPENSE_CREATED',
  'EXPENSE_DELETED',
];

const MODULE_LABELS = {
  auth: 'Authentication',
  users: 'Users & Staff',
  inventory: 'Inventory',
  catalogue: 'Catalogue',
  procurement: 'Procurement',
  sales: 'Sales',
  finance: 'Finance',
  system: 'System',
};

const MODULE_VARIANTS = {
  auth: 'info',
  users: 'brand',
  inventory: 'success',
  catalogue: 'warning',
  procurement: 'info',
  sales: 'brand',
  finance: 'warning',
  system: 'neutral',
};

const TONE_CLASSES = {
  brand: 'bg-brand-50 text-brand-700 border-brand-100',
  info: 'bg-sky-50 text-sky-700 border-sky-100',
  success: 'bg-emerald-50 text-emerald-700 border-emerald-100',
  warning: 'bg-amber-50 text-amber-700 border-amber-100',
};

const EMPTY_FILTERS = {
  module: '',
  action: '',
  userId: '',
  startDate: '',
  endDate: '',
};

function humanize(value) {
  if (!value) return 'Unknown';
  return String(value)
    .toLowerCase()
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function moduleLabel(value) {
  return MODULE_LABELS[value] || humanize(value);
}

function actionVariant(action) {
  const value = String(action || '').toUpperCase();
  if (
    value.includes('FAILED') ||
    value.includes('LOCKED') ||
    value.includes('DELETE') ||
    value.includes('DEACTIVATED')
  ) {
    return 'danger';
  }
  if (
    value.includes('CREATED') ||
    value.includes('SUCCESS') ||
    value.includes('UNLOCK')
  ) {
    return 'success';
  }
  if (value.includes('UPDATED') || value.includes('CHANGE')) {
    return 'warning';
  }
  return 'neutral';
}

function parseAuditDate(value) {
  if (!value) return null;
  const normalized = String(value).includes('T')
    ? String(value)
    : String(value).replace(' ', 'T');
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatAuditDateTime(value) {
  const date = parseAuditDate(value);
  if (!date) return '—';
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

function formatAuditDate(value) {
  const date = parseAuditDate(value);
  if (!date) return '—';
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

function formatAuditTime(value) {
  const date = parseAuditDate(value);
  if (!date) return '';
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}

function shortenId(value, length = 10) {
  if (!value) return '—';
  const text = String(value);
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function prettyJson(value) {
  if (value === null || value === undefined) return null;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function SummaryCard({ label, value, hint, icon: Icon, tone }) {
  return (
    <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-soft-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-slate-500 font-medium">{label}</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
          <div className="text-xs text-slate-400 mt-1">{hint}</div>
        </div>
        <div
          className={`w-10 h-10 rounded-lg border flex items-center justify-center shrink-0 ${TONE_CLASSES[tone] || TONE_CLASSES.brand}`}
        >
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}

function SnapshotBlock({ title, value }) {
  const serialized = useMemo(() => prettyJson(value), [value]);
  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase tracking-wide">
        {title}
      </div>
      {serialized ? (
        <pre className="p-3 text-xs leading-relaxed bg-slate-950/95 text-slate-100 overflow-x-auto max-h-72 whitespace-pre-wrap break-words">
          {serialized}
        </pre>
      ) : (
        <div className="p-3 text-xs text-slate-400">No value snapshot recorded.</div>
      )}
    </div>
  );
}

export function AuditLogsPage() {
  useDocumentTitle('Audit Logs');

  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [stats, setStats] = useState(null);
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(25);

  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const [options, setOptions] = useState({
    modules: FALLBACK_MODULES,
    actions: FALLBACK_ACTIONS,
    users: [],
  });
  const [optionsError, setOptionsError] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearch(searchInput.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const loadOptions = useCallback(async () => {
    setOptionsError(null);
    try {
      const data = await getAuditLogOptions();
      setOptions({
        modules: data?.modules?.length ? data.modules : FALLBACK_MODULES,
        actions: data?.actions?.length ? data.actions : FALLBACK_ACTIONS,
        users: data?.users || [],
      });
    } catch (err) {
      setOptionsError(err?.message || 'Filter options could not be loaded.');
      setOptions((current) => ({
        ...current,
        modules: current.modules?.length ? current.modules : FALLBACK_MODULES,
        actions: current.actions?.length ? current.actions : FALLBACK_ACTIONS,
      }));
    }
  }, []);

  useEffect(() => {
    loadOptions();
  }, [loadOptions]);

  const loadLogs = useCallback(async () => {
    if (filters.startDate && filters.endDate && filters.startDate > filters.endDate) {
      setError('Start date must be on or before the end date.');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await getAuditLogs({
        search,
        module: filters.module,
        action: filters.action,
        userId: filters.userId,
        startDate: filters.startDate,
        endDate: filters.endDate,
        page,
        limit,
      });
      setLogs(response?.logs || []);
      setTotal(response?.total ?? 0);
      setTotalPages(response?.total_pages ?? 0);
      setStats(response?.stats || null);
      setPage(response?.page ?? page);
    } catch (err) {
      setError(err?.message || 'Failed to load audit logs.');
    } finally {
      setIsLoading(false);
    }
  }, [filters, limit, page, search]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  useEffect(() => {
    if (!selectedId) return undefined;
    let cancelled = false;

    setDetailLoading(true);
    setDetail(null);
    setDetailError(null);

    getAuditLogById(selectedId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((err) => {
        if (!cancelled) setDetailError(err?.message || 'Failed to load audit event details.');
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return undefined;
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setSelectedId(null);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedId]);

  const setFilter = (name, value) => {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setSearchInput('');
    setSearch('');
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const hasActiveFilters =
    Boolean(search) ||
    Boolean(filters.module) ||
    Boolean(filters.action) ||
    Boolean(filters.userId) ||
    Boolean(filters.startDate) ||
    Boolean(filters.endDate);

  const rangeStart = total === 0 ? 0 : (page - 1) * limit + 1;
  const rangeEnd = total === 0 ? 0 : Math.min(page * limit, total);
  const displayTotalPages = Math.max(totalPages, 1);

  const summaryCards = [
    {
      label: 'Total Audit Events',
      value: stats ? stats.total.toLocaleString('en-IN') : '—',
      hint: 'Immutable records retained',
      icon: FileText,
      tone: 'brand',
    },
    {
      label: 'Events Today',
      value: stats ? stats.today.toLocaleString('en-IN') : '—',
      hint: 'Recorded since midnight',
      icon: Calendar,
      tone: 'info',
    },
    {
      label: 'Unique Actors',
      value: stats ? stats.actors.toLocaleString('en-IN') : '—',
      hint: 'Users and system events',
      icon: Users,
      tone: 'success',
    },
    {
      label: 'Active Modules',
      value: stats ? stats.modules.toLocaleString('en-IN') : '—',
      hint: 'Instrumented business areas',
      icon: Layers,
      tone: 'warning',
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Logs"
        subtitle="Immutable, administrator-only history of authentication, staff, inventory, sales, procurement, and finance activity"
        badge={
          <Badge variant="brand" size="md" dot>
            Audit Trail
          </Badge>
        }
        actions={
          <Button
            variant="outline"
            size="sm"
            icon={RefreshCw}
            onClick={() => {
              loadLogs();
              loadOptions();
            }}
            disabled={isLoading}
          >
            Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {summaryCards.map((card) => (
          <SummaryCard key={card.label} {...card} />
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="px-5 py-4 border-b border-slate-100 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search description, actor, action, entity ID..."
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  className="w-full pl-9 pr-9 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
                {searchInput && (
                  <button
                    type="button"
                    onClick={() => setSearchInput('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-600"
                    aria-label="Clear search"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                icon={Filter}
                onClick={clearFilters}
                disabled={!hasActiveFilters}
              >
                Clear Filters
              </Button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                  Module
                </label>
                <select
                  value={filters.module}
                  onChange={(event) => setFilter('module', event.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">All Modules</option>
                  {(options.modules || []).map((moduleName) => (
                    <option key={moduleName} value={moduleName}>
                      {moduleLabel(moduleName)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                  Action
                </label>
                <select
                  value={filters.action}
                  onChange={(event) => setFilter('action', event.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">All Actions</option>
                  {(options.actions || []).map((action) => (
                    <option key={action} value={action}>
                      {humanize(action)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                  User / Actor
                </label>
                <select
                  value={filters.userId}
                  onChange={(event) => setFilter('userId', event.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="">All Users</option>
                  {(options.users || []).map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.name || 'Unknown user'}
                      {user.role ? ` (${humanize(user.role)})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={filters.startDate}
                  max={filters.endDate || undefined}
                  onChange={(event) => setFilter('startDate', event.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={filters.endDate}
                  min={filters.startDate || undefined}
                  onChange={(event) => setFilter('endDate', event.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>
          </div>

          {error && (
            <div className="mx-5 my-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {optionsError && !error && (
            <div className="mx-5 my-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{optionsError} Showing standard filter options instead.</span>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th className="py-3 px-5 font-semibold">Timestamp</th>
                  <th className="py-3 px-4 font-semibold">Actor</th>
                  <th className="py-3 px-4 font-semibold">Module</th>
                  <th className="py-3 px-4 font-semibold">Action</th>
                  <th className="py-3 px-4 font-semibold">Description</th>
                  <th className="py-3 px-4 font-semibold">Entity</th>
                  <th className="py-3 px-5 font-semibold text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                      Loading audit trail...
                    </td>
                  </tr>
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <ShieldCheck className="w-8 h-8 mx-auto text-slate-300 mb-2" />
                      <div className="font-medium text-slate-500">No audit events found</div>
                      <div className="text-xs mt-1">
                        {hasActiveFilters
                          ? 'Try clearing one or more filters.'
                          : 'Audit activity will appear here as business operations occur.'}
                      </div>
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr
                      key={log.id}
                      className="hover:bg-slate-50/70 transition-colors cursor-pointer"
                      onClick={() => setSelectedId(log.id)}
                    >
                      <td className="py-3.5 px-5 whitespace-nowrap">
                        <div className="text-xs font-medium text-slate-700">
                          {formatAuditDate(log.created_at)}
                        </div>
                        <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                          <Clock className="w-3 h-3" />
                          {formatAuditTime(log.created_at)}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-slate-900 max-w-[12rem] truncate">
                          {log.actor_name || 'System'}
                        </div>
                        <div className="text-[11px] text-slate-400 capitalize">
                          {log.actor_role || 'system'}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <Badge variant={MODULE_VARIANTS[log.module] || 'neutral'} size="sm">
                          {moduleLabel(log.module)}
                        </Badge>
                      </td>
                      <td className="py-3.5 px-4">
                        <Badge variant={actionVariant(log.action)} size="sm">
                          {humanize(log.action)}
                        </Badge>
                      </td>
                      <td className="py-3.5 px-4 max-w-sm">
                        <div className="text-slate-700 truncate" title={log.description || ''}>
                          {log.description || '—'}
                        </div>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="text-xs text-slate-600 capitalize">
                          {humanize(log.entity_type)}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono" title={log.entity_id || ''}>
                          {shortenId(log.entity_id)}
                        </div>
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedId(log.id);
                          }}
                          className="p-1.5 text-slate-500 hover:text-brand-600 hover:bg-brand-50 rounded-md transition-colors"
                          title="View audit event details"
                          aria-label={`View details for ${log.action || 'audit event'}`}
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

          <div className="px-5 py-3 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-500">
            <div>
              Showing {rangeStart}–{rangeEnd} of {total.toLocaleString('en-IN')} audit events
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1.5">
                <span>Rows</span>
                <select
                  value={limit}
                  onChange={(event) => {
                    setLimit(Number(event.target.value));
                    setPage(1);
                  }}
                  className="px-2 py-1.5 border border-slate-200 rounded-lg text-xs bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                variant="outline"
                size="sm"
                icon={ChevronLeft}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                disabled={page <= 1 || isLoading}
              >
                Previous
              </Button>
              <span className="px-1">
                Page {page} of {displayTotalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                icon={ChevronRight}
                iconPosition="right"
                onClick={() => setPage((current) => Math.min(displayTotalPages, current + 1))}
                disabled={page >= displayTotalPages || isLoading || total === 0}
              >
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {selectedId && (
        <div
          className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setSelectedId(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="audit-detail-title"
            className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-scale-in"
          >
            <div className="px-6 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-700 border border-brand-100 flex items-center justify-center shrink-0">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 id="audit-detail-title" className="font-semibold text-slate-900 text-base">
                    Audit Event Details
                  </h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">{selectedId}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                aria-label="Close audit details"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {detailLoading ? (
                <div className="py-12 text-center text-slate-400">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
                  Loading event details...
                </div>
              ) : detailError ? (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-sm flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{detailError}</span>
                </div>
              ) : detail ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={MODULE_VARIANTS[detail.module] || 'neutral'} size="md">
                      {moduleLabel(detail.module)}
                    </Badge>
                    <Badge variant={actionVariant(detail.action)} size="md">
                      {humanize(detail.action)}
                    </Badge>
                    <Badge variant="neutral" size="md">
                      {formatAuditDateTime(detail.created_at)}
                    </Badge>
                  </div>

                  {detail.description && (
                    <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-700">
                      {detail.description}
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                        Actor
                      </div>
                      <div className="text-sm font-medium text-slate-900 mt-0.5">
                        {detail.actor_name || 'System'}
                      </div>
                      <div className="text-xs text-slate-500 capitalize">{detail.actor_role || 'system'}</div>
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                        Actor ID
                      </div>
                      <div className="text-xs font-mono text-slate-700 mt-1 break-all">
                        {detail.user_id || '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                        Entity
                      </div>
                      <div className="text-sm font-medium text-slate-900 mt-0.5">
                        {humanize(detail.entity_type)}
                      </div>
                      <div className="text-xs font-mono text-slate-500 break-all">
                        {detail.entity_id || '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                        Recorded At
                      </div>
                      <div className="text-sm text-slate-800 mt-0.5">
                        {formatAuditDateTime(detail.created_at)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                        IP Address
                      </div>
                      <div className="text-xs font-mono text-slate-700 mt-1">
                        {detail.ip_address || '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide">
                        User Agent
                      </div>
                      <div className="text-xs text-slate-600 mt-1 break-words">
                        {detail.user_agent || '—'}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-1">
                    <SnapshotBlock title="Previous Values" value={detail.old_values} />
                    <SnapshotBlock title="New Values" value={detail.new_values} />
                  </div>
                </>
              ) : (
                <div className="py-10 text-center text-sm text-slate-400">
                  Audit event not found.
                </div>
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-100 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setSelectedId(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AuditLogsPage;
