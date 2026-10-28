-- ==============================================================================
-- MediShop: Medical Shop Management System
-- Phase 2: Database Schema & Security Foundation Migration
-- Version: 20261027000000_initial_schema.sql
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. ENUMS & CUSTOM TYPES
DO $$ BEGIN
  CREATE TYPE public.app_role AS ENUM ('admin', 'pharmacist');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE public.movement_type AS ENUM (
    'purchase_in',
    'sale_out',
    'return_in',
    'return_to_supplier',
    'expired_disposal',
    'damaged_write_off',
    'inventory_adjustment'
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE public.payment_method AS ENUM (
    'cash',
    'upi',
    'card',
    'credit',
    'split'
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE public.payment_status AS ENUM (
    'paid',
    'pending',
    'partial',
    'cancelled'
  );
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

-- 3. UTILITY FUNCTIONS (UPDATED_AT TRIGGER & SECURITY DEFINER HELPERS)

-- Standard trigger function to auto-update 'updated_at' columns
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- Secure helper function to check if the current authenticated user has 'admin' role
-- STABLE + SET search_path = '' ensures security and avoids infinite recursion in RLS
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE id = auth.uid()
      AND role = 'admin'
      AND is_active = true
  );
$$;

-- Secure helper function to check if user is active staff (admin or pharmacist)
CREATE OR REPLACE FUNCTION public.is_staff()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE id = auth.uid()
      AND is_active = true
  );
$$;

-- ==============================================================================
-- 4. TABLE DEFINITIONS
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Table 1: PROFILES (Extends Supabase auth.users with medical store staff roles)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name text NOT NULL,
  role public.app_role NOT NULL DEFAULT 'pharmacist',
  phone text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Trigger for profiles updated_at
CREATE TRIGGER set_profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Trigger to automatically create a profile entry when a user signs up via Supabase Auth
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', 'Pharmacy Staff'),
    'pharmacist' -- New signups are always assigned the lowest privilege ('pharmacist') by default
  );
  RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ------------------------------------------------------------------------------
-- Table 2: CATEGORIES (Therapeutic drug classes & storage requirements)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  slug text NOT NULL UNIQUE,
  description text,
  storage_temperature text DEFAULT 'Room Temperature',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_categories_updated_at
  BEFORE UPDATE ON public.categories
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 3: BRANDS (Pharmaceutical manufacturers & marketing companies)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.brands (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  manufacturer text,
  contact_email text,
  contact_phone text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_brands_updated_at
  BEFORE UPDATE ON public.brands
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 4: MEDICINES (Master drug catalogue & clinical classifications)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.medicines (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  generic_name text,
  category_id uuid NOT NULL REFERENCES public.categories(id) ON DELETE RESTRICT,
  brand_id uuid REFERENCES public.brands(id) ON DELETE SET NULL,
  dosage_form text NOT NULL, -- e.g. Tablet, Capsule, Syrup, Injection, Ointment, Drops, Inhaler, Other
  strength text,            -- e.g. 500mg, 10ml, 250mg/5ml
  unit text NOT NULL DEFAULT 'Strip', -- e.g. Strip, Bottle, Box, Vial, Piece
  hsn_code text,
  requires_prescription boolean NOT NULL DEFAULT false, -- Schedule H/X compliance flag
  min_stock_alert integer NOT NULL DEFAULT 10 CHECK (min_stock_alert >= 0),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_medicines_updated_at
  BEFORE UPDATE ON public.medicines
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 5: SUPPLIERS (Wholesale distributors, pharma stockists, licenses)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.suppliers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  contact_person text,
  phone text NOT NULL,
  email text,
  address text,
  gstin text,
  drug_license_no text,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_suppliers_updated_at
  BEFORE UPDATE ON public.suppliers
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 6: PURCHASES (Inward purchase bills from suppliers)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.purchases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_no text NOT NULL, -- Vendor bill number
  supplier_id uuid NOT NULL REFERENCES public.suppliers(id) ON DELETE RESTRICT,
  purchase_date date NOT NULL DEFAULT CURRENT_DATE,
  total_amount numeric(12,2) NOT NULL CHECK (total_amount >= 0),
  tax_amount numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (tax_amount >= 0),
  discount_amount numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
  net_amount numeric(12,2) NOT NULL CHECK (net_amount >= 0),
  payment_status public.payment_status NOT NULL DEFAULT 'paid',
  notes text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_supplier_invoice UNIQUE(supplier_id, invoice_no)
);

CREATE TRIGGER set_purchases_updated_at
  BEFORE UPDATE ON public.purchases
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 7: BATCHES (Medicine batches tracking lot, expiry, costs, stock)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.batches (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  medicine_id uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  supplier_id uuid REFERENCES public.suppliers(id) ON DELETE SET NULL,
  batch_no text NOT NULL,
  mfg_date date,
  expiry_date date NOT NULL,
  purchase_cost numeric(12,2) NOT NULL CHECK (purchase_cost >= 0), -- Cost per unit
  mrp numeric(12,2) NOT NULL CHECK (mrp >= 0),                     -- Maximum retail price
  selling_price numeric(12,2) NOT NULL CHECK (selling_price >= 0), -- Counter selling price
  initial_quantity integer NOT NULL CHECK (initial_quantity >= 0),
  current_quantity integer NOT NULL DEFAULT 0 CHECK (current_quantity >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT check_expiry_after_mfg CHECK (mfg_date IS NULL OR expiry_date > mfg_date),
  CONSTRAINT check_selling_price_within_mrp CHECK (selling_price <= mrp),
  CONSTRAINT uq_medicine_batch UNIQUE(medicine_id, batch_no)
);

CREATE TRIGGER set_batches_updated_at
  BEFORE UPDATE ON public.batches
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 8: PURCHASE_ITEMS (Line items in a purchase bill linking batch & medicine)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.purchase_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_id uuid NOT NULL REFERENCES public.purchases(id) ON DELETE CASCADE,
  medicine_id uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  batch_id uuid NOT NULL REFERENCES public.batches(id) ON DELETE RESTRICT,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_cost numeric(12,2) NOT NULL CHECK (unit_cost >= 0),
  tax_rate numeric(5,2) NOT NULL DEFAULT 0.00 CHECK (tax_rate >= 0),
  subtotal numeric(12,2) NOT NULL CHECK (subtotal >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- Table 9: CUSTOMERS (Patients and recurring clients)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  phone text UNIQUE,
  email text,
  address text,
  doctor_name text, -- Referring physician
  allergies_or_notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_customers_updated_at
  BEFORE UPDATE ON public.customers
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 10: INVOICES (Sales receipts generated at counter POS)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invoices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_no text NOT NULL UNIQUE,
  customer_id uuid REFERENCES public.customers(id) ON DELETE SET NULL,
  total_amount numeric(12,2) NOT NULL CHECK (total_amount >= 0),
  tax_amount numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (tax_amount >= 0),
  discount_amount numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
  net_amount numeric(12,2) NOT NULL CHECK (net_amount >= 0),
  payment_method public.payment_method NOT NULL DEFAULT 'cash',
  payment_status public.payment_status NOT NULL DEFAULT 'paid',
  doctor_prescription_ref text,
  notes text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_invoices_updated_at
  BEFORE UPDATE ON public.invoices
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 11: INVOICE_ITEMS (Line items in a sale invoice with cost snapshot)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invoice_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id uuid NOT NULL REFERENCES public.invoices(id) ON DELETE CASCADE,
  medicine_id uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  batch_id uuid NOT NULL REFERENCES public.batches(id) ON DELETE RESTRICT,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
  purchase_cost_at_sale numeric(12,2) NOT NULL CHECK (purchase_cost_at_sale >= 0), -- Snapshot for exact historical profit
  tax_rate numeric(5,2) NOT NULL DEFAULT 0.00 CHECK (tax_rate >= 0),
  discount_amount numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
  subtotal numeric(12,2) NOT NULL CHECK (subtotal >= 0),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- Table 12: EXPENSES (Store operational expenditures & petty cash)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.expenses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  category text NOT NULL, -- e.g. Rent, Electricity, Salaries, Refrigerator maintenance
  amount numeric(12,2) NOT NULL CHECK (amount > 0),
  expense_date date NOT NULL DEFAULT CURRENT_DATE,
  payment_method text NOT NULL DEFAULT 'cash',
  receipt_url text,
  notes text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER set_expenses_updated_at
  BEFORE UPDATE ON public.expenses
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 13: STOCK_MOVEMENTS (Immutable audit trail of all inventory alterations)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_movements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  medicine_id uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  batch_id uuid NOT NULL REFERENCES public.batches(id) ON DELETE RESTRICT,
  movement_type public.movement_type NOT NULL,
  quantity_change integer NOT NULL CHECK (quantity_change != 0), -- Positive for additions, negative for deductions
  quantity_before integer NOT NULL CHECK (quantity_before >= 0),
  quantity_after integer NOT NULL CHECK (quantity_after >= 0),
  reference_id uuid, -- Pointer to invoice_id, purchase_id, etc.
  reference_type text, -- e.g. 'invoice', 'purchase', 'manual_adjustment'
  reason text,
  created_by uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- Table 14: AUDIT_LOGS (Immutable administrative activity log)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  action text NOT NULL, -- e.g. 'CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'ROLE_CHANGE', 'PRICE_OVERRIDE'
  table_name text NOT NULL,
  record_id uuid,
  old_data jsonb,
  new_data jsonb,
  ip_address text,
  user_agent text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ==============================================================================
-- 5. PERFORMANCE & FEFO INDEXES
-- ==============================================================================

-- Medicines & Search Indexes
CREATE INDEX IF NOT EXISTS idx_medicines_category ON public.medicines(category_id);
CREATE INDEX IF NOT EXISTS idx_medicines_brand ON public.medicines(brand_id);
CREATE INDEX IF NOT EXISTS idx_medicines_name ON public.medicines(name);
CREATE INDEX IF NOT EXISTS idx_medicines_generic_name ON public.medicines(generic_name);
CREATE INDEX IF NOT EXISTS idx_medicines_min_stock ON public.medicines(min_stock_alert) WHERE is_active = true;

-- Batches, Expiry & FEFO (First Expiry, First Out) Indexes
-- Compound index optimized for dispensing: finds available stock ordered by earliest expiration date
CREATE INDEX IF NOT EXISTS idx_batches_fefo ON public.batches(medicine_id, expiry_date ASC, current_quantity)
  WHERE current_quantity > 0;
CREATE INDEX IF NOT EXISTS idx_batches_expiry ON public.batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_batches_supplier ON public.batches(supplier_id);

-- Purchases & Items
CREATE INDEX IF NOT EXISTS idx_purchases_supplier ON public.purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON public.purchases(purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON public.purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_medicine ON public.purchase_items(medicine_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_batch ON public.purchase_items(batch_id);

-- Invoices & Sales Reporting
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON public.invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON public.invoices(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_no ON public.invoices(invoice_no);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON public.invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_medicine ON public.invoice_items(medicine_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_batch ON public.invoice_items(batch_id);

-- Stock Movements & Audits
CREATE INDEX IF NOT EXISTS idx_stock_movements_medicine ON public.stock_movements(medicine_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_movements_batch ON public.stock_movements(batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_ref ON public.stock_movements(reference_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON public.audit_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_table ON public.audit_logs(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON public.expenses(expense_date DESC);

-- ==============================================================================
-- 6. ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

-- Enable RLS on every table
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medicines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------------------------
-- RLS: PROFILES
-- ------------------------------------------------------------------------------
-- Active staff can read profiles (to see names/roles on sales and audit logs)
CREATE POLICY "profiles_select_staff"
  ON public.profiles FOR SELECT
  TO authenticated
  USING (public.is_staff());

-- Users can update only their own phone/name; CANNOT alter their own role
CREATE POLICY "profiles_update_self"
  ON public.profiles FOR UPDATE
  TO authenticated
  USING (id = auth.uid())
  WITH CHECK (
    id = auth.uid()
    AND role = (SELECT role FROM public.profiles WHERE id = auth.uid()) -- Prevents self-elevation
  );

-- Only Admin can update any profile (including role changes and deactivations)
CREATE POLICY "profiles_admin_all"
  ON public.profiles FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: CATEGORIES & BRANDS
-- ------------------------------------------------------------------------------
CREATE POLICY "categories_select_staff"
  ON public.categories FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "categories_admin_modify"
  ON public.categories FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

CREATE POLICY "brands_select_staff"
  ON public.brands FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "brands_admin_modify"
  ON public.brands FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: MEDICINES
-- ------------------------------------------------------------------------------
CREATE POLICY "medicines_select_staff"
  ON public.medicines FOR SELECT
  TO authenticated
  USING (public.is_staff());

-- Admins have full CRUD; Pharmacists can add new drugs if authorized, but cannot delete
CREATE POLICY "medicines_admin_all"
  ON public.medicines FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

CREATE POLICY "medicines_pharmacist_insert"
  ON public.medicines FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

CREATE POLICY "medicines_pharmacist_update"
  ON public.medicines FOR UPDATE
  TO authenticated
  USING (public.is_staff())
  WITH CHECK (public.is_staff());

-- ------------------------------------------------------------------------------
-- RLS: SUPPLIERS
-- ------------------------------------------------------------------------------
CREATE POLICY "suppliers_select_staff"
  ON public.suppliers FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "suppliers_admin_modify"
  ON public.suppliers FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: BATCHES
-- ------------------------------------------------------------------------------
-- Staff can view batches for dispensing & inventory tracking
CREATE POLICY "batches_select_staff"
  ON public.batches FOR SELECT
  TO authenticated
  USING (public.is_staff());

-- Admins have full management
CREATE POLICY "batches_admin_all"
  ON public.batches FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- Pharmacists can register new inward batches during stock-in
CREATE POLICY "batches_pharmacist_insert"
  ON public.batches FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

-- ------------------------------------------------------------------------------
-- RLS: PURCHASES & PURCHASE_ITEMS
-- ------------------------------------------------------------------------------
CREATE POLICY "purchases_select_staff"
  ON public.purchases FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "purchases_insert_staff"
  ON public.purchases FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

CREATE POLICY "purchases_admin_modify"
  ON public.purchases FOR UPDATE
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

CREATE POLICY "purchases_admin_delete"
  ON public.purchases FOR DELETE
  TO authenticated
  USING (public.is_admin());

CREATE POLICY "purchase_items_select_staff"
  ON public.purchase_items FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "purchase_items_insert_staff"
  ON public.purchase_items FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

CREATE POLICY "purchase_items_admin_modify"
  ON public.purchase_items FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: CUSTOMERS
-- ------------------------------------------------------------------------------
CREATE POLICY "customers_select_staff"
  ON public.customers FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "customers_insert_staff"
  ON public.customers FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

CREATE POLICY "customers_update_staff"
  ON public.customers FOR UPDATE
  TO authenticated
  USING (public.is_staff())
  WITH CHECK (public.is_staff());

CREATE POLICY "customers_admin_delete"
  ON public.customers FOR DELETE
  TO authenticated
  USING (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: INVOICES & INVOICE_ITEMS (Counter Sales)
-- ------------------------------------------------------------------------------
CREATE POLICY "invoices_select_staff"
  ON public.invoices FOR SELECT
  TO authenticated
  USING (public.is_staff());

-- Any active staff member can issue a sales invoice
CREATE POLICY "invoices_insert_staff"
  ON public.invoices FOR INSERT
  TO authenticated
  WITH CHECK (
    public.is_staff()
    AND (created_by IS NULL OR created_by = auth.uid())
  );

-- Invoices cannot be arbitrarily updated or deleted by cashiers once finalized;
-- Only Admins can modify or cancel invoices
CREATE POLICY "invoices_admin_update"
  ON public.invoices FOR UPDATE
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

CREATE POLICY "invoices_admin_delete"
  ON public.invoices FOR DELETE
  TO authenticated
  USING (public.is_admin());

CREATE POLICY "invoice_items_select_staff"
  ON public.invoice_items FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "invoice_items_insert_staff"
  ON public.invoice_items FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

CREATE POLICY "invoice_items_admin_modify"
  ON public.invoice_items FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: EXPENSES
-- ------------------------------------------------------------------------------
CREATE POLICY "expenses_select_staff"
  ON public.expenses FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "expenses_insert_staff"
  ON public.expenses FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

CREATE POLICY "expenses_admin_modify"
  ON public.expenses FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- ------------------------------------------------------------------------------
-- RLS: STOCK_MOVEMENTS
-- ------------------------------------------------------------------------------
-- Read-only audit trail for staff; inserted by business operations
CREATE POLICY "stock_movements_select_staff"
  ON public.stock_movements FOR SELECT
  TO authenticated
  USING (public.is_staff());

CREATE POLICY "stock_movements_insert_staff"
  ON public.stock_movements FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

-- Deletions or updates to stock movement logs are strictly prohibited for audit integrity
-- (No UPDATE or DELETE policy granted to any role)

-- ------------------------------------------------------------------------------
-- RLS: AUDIT_LOGS
-- ------------------------------------------------------------------------------
-- Only Admin can view administrative audit logs
CREATE POLICY "audit_logs_select_admin"
  ON public.audit_logs FOR SELECT
  TO authenticated
  USING (public.is_admin());

-- Any staff action can append an audit log entry
CREATE POLICY "audit_logs_insert_staff"
  ON public.audit_logs FOR INSERT
  TO authenticated
  WITH CHECK (public.is_staff());

-- Deletions or updates to audit logs are strictly prohibited
-- ==============================================================================
