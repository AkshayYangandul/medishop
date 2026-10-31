/**
 * MediShop API Service Layer
 * =============================
 * Thin fetch-based client for the FastAPI backend.
 *
 * Base URL: ``VITE_API_URL`` env var (e.g. ``http://localhost:8000``) when set,
 * otherwise a same-origin relative base (``/api`` paths) so the Vite dev proxy
 * can forward requests to the backend in development.
 *
 * Auth: The backend issues signed HS256 JWT bearer tokens via
 * ``POST /api/auth/login`` and validates them via ``GET /api/auth/me``.
 * Tokens are stored in browser storage (localStorage when "remember me" is
 * checked, sessionStorage otherwise) and sent as ``Authorization: Bearer <token>``.
 *
 * Security note: The backend does NOT use httpOnly cookies today, so the access
 * token must live in browser storage accessible to JavaScript. This is stored
 * XSS-readable by design; httpOnly cookie + refresh-token rotation would be the
 * more secure long-term direction. Until then, keep this client as the only
 * place the token is read/written and never log it.
 */

const API_BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');

const TOKEN_KEY = 'medishop_access_token';

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ---------------------------------------------------------------------------
// Token storage helpers (localStorage vs sessionStorage via `rememberMe`)
// ---------------------------------------------------------------------------

export function getAccessToken() {
  if (typeof window === 'undefined') return null;
  const token =
    window.localStorage.getItem(TOKEN_KEY) ||
    window.sessionStorage.getItem(TOKEN_KEY);
  return token || null;
}

export function setAccessToken(token, persist = true) {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(TOKEN_KEY);
  if (token) {
    if (persist) {
      window.localStorage.setItem(TOKEN_KEY, token);
    } else {
      window.sessionStorage.setItem(TOKEN_KEY, token);
    }
  }
}

export function clearAccessToken() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// JWT helpers (decode payload only — signature is verified server-side)
// ---------------------------------------------------------------------------

function decodeTokenPayload(token) {
  try {
    const payloadPart = token.split('.')[1];
    const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const json = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function isTokenExpired(token) {
  if (!token) return true;
  const payload = decodeTokenPayload(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  return payload.exp * 1000 <= Date.now();
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function apiRequest(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  const activeToken = token || getAccessToken();
  if (activeToken) {
    headers['Authorization'] = `Bearer ${activeToken}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Unable to reach the MediShop server. Please check your connection and try again.');
  }

  let data = null;
  const raw = await response.text();
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    const detail = (data && data.detail) || 'An unexpected error occurred. Please try again.';
    throw new ApiError(response.status, detail);
  }

  return data;
}

// ---------------------------------------------------------------------------
// Auth API functions
// ---------------------------------------------------------------------------

/**
 * Authenticates against POST /api/auth/login.
 * Stores the returned bearer token and hydrates the user via GET /api/auth/me.
 * Throws ApiError with a user-friendly message on failure.
 */
export async function login({ email, password, rememberMe = true }) {
  const data = await apiRequest('/api/auth/login', {
    method: 'POST',
    body: { email, password },
  });

  const accessToken = data?.access_token;
  if (!accessToken) {
    throw new ApiError(401, 'Authentication failed. Please try again.');
  }

  setAccessToken(accessToken, rememberMe);

  const user = await getCurrentUser(accessToken);
  return { token: accessToken, user };
}

/**
 * Fetches the currently authenticated user via GET /api/auth/me.
 * Clears the stored token when the session is missing, malformed, or expired.
 */
export async function getCurrentUser(token) {
  const activeToken = token || getAccessToken();
  if (!activeToken) {
    throw new ApiError(401, 'Your session has expired. Please sign in again.');
  }

  if (isTokenExpired(activeToken)) {
    clearAccessToken();
    throw new ApiError(401, 'Your session has expired. Please sign in again.');
  }

  const user = await apiRequest('/api/auth/me', { token: activeToken });
  return user;
}

// ---------------------------------------------------------------------------
// Medicine & inventory API functions
// ---------------------------------------------------------------------------

export async function getMedicines({ search, categoryId, brandId, isActive, page, limit } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (categoryId) params.set('category_id', categoryId);
  if (brandId) params.set('brand_id', brandId);
  if (isActive !== undefined) params.set('is_active', String(isActive));
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));

  const queryString = params.toString();
  return apiRequest(`/api/medicines${queryString ? `?${queryString}` : ''}`);
}

export async function getMedicineById(medicineId) {
  return apiRequest(`/api/medicines/${medicineId}`);
}

export async function createMedicine(data) {
  return apiRequest('/api/medicines', { method: 'POST', body: data });
}

export async function updateMedicine(medicineId, data) {
  return apiRequest(`/api/medicines/${medicineId}`, { method: 'PATCH', body: data });
}

export async function getMedicineInventory(medicineId) {
  return apiRequest(`/api/inventory/medicines/${medicineId}`);
}

export async function getMedicinesInventory({ search, isActive, page, limit } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (isActive !== undefined) params.set('is_active', String(isActive));
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));

  const queryString = params.toString();
  return apiRequest(`/api/inventory/medicines${queryString ? `?${queryString}` : ''}`);
}

export async function getMedicineCategories() {
  return apiRequest('/api/categories');
}

export async function createCategory(data) {
  return apiRequest('/api/categories', { method: 'POST', body: data });
}

export async function updateCategory(categoryId, data) {
  return apiRequest(`/api/categories/${categoryId}`, { method: 'PATCH', body: data });
}

export async function deleteCategory(categoryId) {
  return apiRequest(`/api/categories/${categoryId}`, { method: 'DELETE' });
}

export async function getMedicineBrands() {
  return apiRequest('/api/brands');
}

export async function createBrand(data) {
  return apiRequest('/api/brands', { method: 'POST', body: data });
}

export async function updateBrand(brandId, data) {
  return apiRequest(`/api/brands/${brandId}`, { method: 'PATCH', body: data });
}

export async function deleteBrand(brandId) {
  return apiRequest(`/api/brands/${brandId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Batches API functions
// ---------------------------------------------------------------------------

export async function getBatches({ search, medicineId, statusFilter, page, limit } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (medicineId) params.set('medicine_id', medicineId);
  if (statusFilter) params.set('status_filter', statusFilter);
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));

  const queryString = params.toString();
  return apiRequest(`/api/batches${queryString ? `?${queryString}` : ''}`);
}

export async function createBatch(data) {
  return apiRequest('/api/batches', { method: 'POST', body: data });
}

// ---------------------------------------------------------------------------
// Suppliers API functions
// ---------------------------------------------------------------------------

export async function getSuppliers({ search } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  const queryString = params.toString();
  return apiRequest(`/api/suppliers${queryString ? `?${queryString}` : ''}`);
}

export async function getSupplierById(supplierId) {
  return apiRequest(`/api/suppliers/${supplierId}`);
}

export async function createSupplier(data) {
  return apiRequest('/api/suppliers', { method: 'POST', body: data });
}

export async function updateSupplier(supplierId, data) {
  return apiRequest(`/api/suppliers/${supplierId}`, { method: 'PATCH', body: data });
}

export async function deleteSupplier(supplierId) {
  return apiRequest(`/api/suppliers/${supplierId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Customers API functions
// ---------------------------------------------------------------------------

export async function getCustomers({ search } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  const queryString = params.toString();
  return apiRequest(`/api/customers${queryString ? `?${queryString}` : ''}`);
}

export async function getCustomerById(customerId) {
  return apiRequest(`/api/customers/${customerId}`);
}

export async function createCustomer(data) {
  return apiRequest('/api/customers', { method: 'POST', body: data });
}

export async function updateCustomer(customerId, data) {
  return apiRequest(`/api/customers/${customerId}`, { method: 'PATCH', body: data });
}

export async function deleteCustomer(customerId) {
  return apiRequest(`/api/customers/${customerId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Counter Sales (POS) & Invoices API functions
// ---------------------------------------------------------------------------

export async function getInvoices({ search, startDate, endDate, page, limit } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));

  const queryString = params.toString();
  return apiRequest(`/api/invoices${queryString ? `?${queryString}` : ''}`);
}

export async function getInvoiceById(invoiceId) {
  return apiRequest(`/api/invoices/${invoiceId}`);
}

export async function createInvoice(data) {
  return apiRequest('/api/invoices', { method: 'POST', body: data });
}

// ---------------------------------------------------------------------------
// Purchases / Inward Procurement API functions
// ---------------------------------------------------------------------------

export async function getPurchases({ search, page, limit } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));

  const queryString = params.toString();
  return apiRequest(`/api/purchases${queryString ? `?${queryString}` : ''}`);
}

export async function getPurchaseById(purchaseId) {
  return apiRequest(`/api/purchases/${purchaseId}`);
}

export async function createPurchase(data) {
  return apiRequest('/api/purchases', { method: 'POST', body: data });
}

// ---------------------------------------------------------------------------
// Expenses API functions
// ---------------------------------------------------------------------------

export async function getExpenses({ search, category, startDate, endDate, page, limit } = {}) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  if (category) params.set('category', category);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));

  const queryString = params.toString();
  return apiRequest(`/api/expenses${queryString ? `?${queryString}` : ''}`);
}

export async function createExpense(data) {
  return apiRequest('/api/expenses', { method: 'POST', body: data });
}

export async function deleteExpense(expenseId) {
  return apiRequest(`/api/expenses/${expenseId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Users & Staff API functions
// ---------------------------------------------------------------------------

export async function getUsers() {
  return apiRequest('/api/users');
}

export async function createUser(data) {
  return apiRequest('/api/users', { method: 'POST', body: data });
}

export async function updateUserRole(userId, role) {
  return apiRequest(`/api/users/${userId}/role`, { method: 'PATCH', body: { role } });
}

export async function updateUserStatus(userId, isActive) {
  return apiRequest(`/api/users/${userId}/status`, { method: 'PATCH', body: { is_active: isActive } });
}

// ---------------------------------------------------------------------------
// Dashboard & Reports API functions
// ---------------------------------------------------------------------------

export async function getDashboardStats() {
  return apiRequest('/api/dashboard/stats');
}

export async function getReportsSummary({ startDate, endDate } = {}) {
  const params = new URLSearchParams();
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  const queryString = params.toString();
  return apiRequest(`/api/reports/summary${queryString ? `?${queryString}` : ''}`);
}
