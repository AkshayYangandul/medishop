-- ==============================================================================
-- MediShop: Medical Shop Management System
-- Phase 2: Hardened Database Schema, Security & Immutable Audit Foundation
-- Version: 20261027000005_initial_schema_v5_review.sql
-- Status:  REVIEW COPY — Supersedes v4. All previous migration files preserved.
-- ==============================================================================
-- Changes from v4:
--   FIX A: provision_initial_admin() — added pg_advisory_xact_lock to prevent
--           a race condition where two simultaneous SQL Editor calls could both
--           pass the "no admin exists" check and create two admins.
--   FIX B: enforce_profile_security() — added a last-admin guard that blocks
--           ANY caller (including admins) from demoting or deactivating the
--           sole remaining active administrator, preventing system lockout.
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │  WHAT CHANGED FROM v3 — PLAIN ENGLISH SUMMARY                          │
-- └─────────────────────────────────────────────────────────────────────────┘
--
-- CHANGE 1 — Secure Initial Admin Setup (replaces "first-user-admin" logic)
-- ──────────────────────────────────────────────────────────────────────────
--   PROBLEM IN v3:
--     The first person to register through the MediShop signup page was
--     automatically made admin. This is dangerous because:
--       • A random customer who finds the signup link before the store owner
--         could seize admin control of the system.
--       • A bot or malicious actor who registers first would permanently
--         own the system, even with the advisory lock protection.
--
--   FIX IN v4:
--     ALL new registrations always create an INACTIVE PHARMACIST account,
--     regardless of who signs up first. Nobody becomes admin automatically.
--
--     The legitimate store owner grants themselves admin access using a
--     secure, single-use database function (provision_initial_admin) that
--     can ONLY be called from the Supabase project SQL Editor — a tool
--     only accessible to the project owner with infrastructure-level access.
--
--   HOW THE STORE OWNER SETS UP THE FIRST ADMIN ACCOUNT:
--   ──────────────────────────────────────────────────────
--     Step 1 — Register normally:
--       The store owner registers through the MediShop app signup page.
--       Their account will be created as an inactive pharmacist (normal).
--
--     Step 2 — Open the Supabase SQL Editor:
--       Log in to the Supabase project dashboard (only the project owner
--       has credentials for this):
--         https://supabase.com/dashboard/project/YOUR-PROJECT-ID/sql/new
--
--     Step 3 — Run this ONE command (replace email with yours):
--         SELECT public.provision_initial_admin('owner@yourpharmacy.com');
--
--       The function will return a SUCCESS message confirming your account
--       has been promoted to active admin.
--
--     Step 4 — Log in to MediShop and manage staff:
--       From the Staff Management page you can now activate and assign
--       roles to all other staff members.
--
--   Security guarantees of provision_initial_admin():
--     • Works ONLY when zero active admins exist (single-use, self-locking).
--     • After the first admin is provisioned, calling it again returns ERROR.
--     • The authenticated role (regular app users) CANNOT call this function.
--     • Only the Supabase dashboard user (postgres / service_role) can call it,
--       which requires project-owner-level infrastructure access.
--     • Writes a permanent audit record of the provisioning action.
--
-- CHANGE 2 — Immutable Audit Logging via Database Triggers
-- ──────────────────────────────────────────────────────────
--   PROBLEM IN v3:
--     The audit_logs table existed but was never populated. Nothing was
--     being recorded, so the store owner had no visibility into who changed
--     what in the system.
--
--   FIX IN v4:
--     Two SECURITY DEFINER trigger functions write to audit_logs automatically
--     when important data changes occur. These triggers fire inside the database
--     engine — no user or application code can suppress or bypass them.
--
--   WHAT IS AUDITED:
--     • profiles     — ONLY role and is_active changes (avoids storing PII)
--     • medicines    — INSERT, UPDATE, DELETE (full before/after snapshot)
--     • purchases    — INSERT, UPDATE, DELETE (full before/after snapshot)
--     • invoices     — INSERT, UPDATE, DELETE (full before/after snapshot)
--     • batches      — INSERT, UPDATE (captures all stock quantity changes)
--
--   WHAT IS NOT AUDITED (and why):
--     • customers    — Contains patient PII (name, phone, address, allergies).
--                      Logging full rows unnecessarily duplicates sensitive data.
--     • stock_movements — Is itself an immutable audit ledger. Auditing it
--                      separately would create redundant duplicate entries.
--     • purchase_items, invoice_items — Parent records (purchase/invoice) are
--                      already audited. Line items have no independent lifecycle.
--     • expenses, categories, brands, suppliers — Not in scope for this review;
--                      can be added incrementally in a future migration.
--
--   Security guarantees of audit triggers:
--     • No client (not even admin via REST API) can INSERT/UPDATE/DELETE
--       rows in audit_logs — RLS has no client-facing write policies.
--     • Only SECURITY DEFINER trigger functions (owned by postgres) write
--       to audit_logs, bypassing RLS from within the database engine.
--     • Logs capture auth.uid() of the acting user, so accountability is
--       preserved even when future RPC functions perform the actual writes.
--
-- CHANGE 3 — enforce_profile_security() Trigger Bug Fix
-- ───────────────────────────────────────────────────────
--   PROBLEM IN v3:
--     The BEFORE UPDATE security trigger on profiles blocked ALL updates to
--     role/is_active even from the Supabase SQL Editor, because auth.uid()
--     is NULL in a service-role session, causing is_admin() to return false,
--     and the trigger raised an exception. This meant provision_initial_admin()
--     would be blocked by its own security trigger.
--
--   FIX IN v4:
--     The trigger now explicitly allows updates when auth.uid() IS NULL.
--     A NULL auth.uid() means the operation is coming from a superuser
--     or a SECURITY DEFINER function with postgres-level privileges —
--     these callers are authenticated at the infrastructure level and are
--     more trusted than any API client. All normal API calls (where
--     auth.uid() is always set) still enforce full security checks.
--
-- FUTURE COMPATIBILITY NOTE:
-- ──────────────────────────
--   Phase 3 (create_purchase_rpc) and Phase 4 (create_checkout_invoice_rpc)
--   will be SECURITY DEFINER functions that:
--     1. INSERT into purchases / invoices       → fires audit_purchases / audit_invoices
--     2. UPDATE batches.current_quantity        → fires audit_batches
--     3. INSERT into stock_movements            → (self-auditing, no extra trigger needed)
--   The audit triggers automatically capture auth.uid() of the calling user
--   because the auth JWT context is preserved through SECURITY DEFINER
--   function execution. No changes to the RPC functions are needed for auditing.
-- ==============================================================================


-- ==============================================================================
-- 1. EXTENSIONS
-- ==============================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ==============================================================================
-- 2. ENUMS & CUSTOM TYPES (Idempotent — safe to re-run on existing database)
-- ==============================================================================
DO $$ BEGIN
  CREATE TYPE public.app_role AS ENUM ('admin', 'pharmacist');
EXCEPTION WHEN duplicate_object THEN null;
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
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE public.payment_method AS ENUM (
    'cash',
    'upi',
    'card',
    'credit',
    'split'
  );
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE public.payment_status AS ENUM (
    'paid',
    'pending',
    'partial',
    'cancelled'
  );
EXCEPTION WHEN duplicate_object THEN null;
END $$;


-- ==============================================================================
-- 3. UTILITY FUNCTIONS
-- ==============================================================================

-- Automatic updated_at maintenance trigger
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;


-- ==============================================================================
-- 4. SECURITY HELPER FUNCTIONS
-- ==============================================================================
-- SECURITY DEFINER + SET search_path = '' prevents:
--   (a) search_path hijacking attacks
--   (b) infinite recursion when RLS policies call these functions

-- Returns TRUE only if the current API caller is an active admin
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid()
      AND role = 'admin'
      AND is_active = true
  );
$$;

-- Returns TRUE if the current API caller is any active staff member
CREATE OR REPLACE FUNCTION public.is_staff()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid()
      AND is_active = true
  );
$$;

-- Restrict helper functions: only authenticated API users may call them
REVOKE EXECUTE ON FUNCTION public.is_admin() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.is_admin() TO authenticated;

REVOKE EXECUTE ON FUNCTION public.is_staff() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.is_staff() TO authenticated;


-- ==============================================================================
-- 5. TABLES
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Table 1: PROFILES
-- Linked 1:1 to Supabase auth.users. Stores role and activation status.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id          uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name   text NOT NULL,
  role        public.app_role NOT NULL DEFAULT 'pharmacist',
  phone       text,
  is_active   boolean NOT NULL DEFAULT false, -- Must be manually activated by admin
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_profiles_updated_at ON public.profiles;
CREATE TRIGGER set_profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ── SECURITY TRIGGER: Blocks non-admins from elevating role or activating self,
-- and prevents ANY caller from demoting/deactivating the last active admin. ──
-- FIX from v3: auth.uid() IS NULL guard allows service_role / migration scripts
-- to bypass this check. These callers are authenticated at the infrastructure
-- level (Supabase dashboard access) and are more privileged than any API client.
-- FIX from v4 (FIX B): Last-admin guard — applied after the non-admin block so
-- it catches all callers, including admins trying to remove the final admin.
CREATE OR REPLACE FUNCTION public.enforce_profile_security()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  -- Allow service_role / postgres superuser context (no JWT = no auth.uid()).
  -- This permits provision_initial_admin() and migration scripts to operate.
  IF auth.uid() IS NULL THEN
    RETURN NEW;
  END IF;

  -- For all normal API calls: enforce that only active admins may change
  -- another account's role or activation status.
  IF NOT public.is_admin() THEN
    IF NEW.role IS DISTINCT FROM OLD.role THEN
      RAISE EXCEPTION
        'Unauthorized: Only store administrators can modify user roles. '
        'Contact your store admin to change your role.';
    END IF;
    IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
      RAISE EXCEPTION
        'Unauthorized: Only store administrators can change account activation status. '
        'Contact your store admin to activate or deactivate accounts.';
    END IF;
  END IF;

  -- ── LAST-ADMIN GUARD (FIX B — new in v5) ────────────────────────────────
  -- If the profile being changed IS currently an active admin, AND the update
  -- would remove that admin status (by demotion or deactivation), block it
  -- when no other active admin exists. This applies to ALL callers, including
  -- admins, so the system can never be left in an adminless state.
  IF OLD.role = 'admin' AND OLD.is_active = true
  AND (NEW.role IS DISTINCT FROM OLD.role OR NEW.is_active IS DISTINCT FROM OLD.is_active)
  THEN
    IF NOT EXISTS (
      SELECT 1 FROM public.profiles
      WHERE role = 'admin'
        AND is_active = true
        AND id != OLD.id   -- Exclude the profile currently being updated
    ) THEN
      RAISE EXCEPTION
        'Forbidden: Cannot demote or deactivate the last active administrator. '
        'Promote another staff member to admin first, then make this change.';
    END IF;
  END IF;
  -- ────────────────────────────────────────────────────────────────────────

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS check_profile_security ON public.profiles;
CREATE TRIGGER check_profile_security
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.enforce_profile_security();

-- ── SIGNUP TRIGGER: All new registrations always create inactive pharmacist ──
-- CHANGED from v3: Removed "first user becomes admin" logic entirely.
-- The store owner uses provision_initial_admin() (Section 6) instead.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role, is_active)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', 'Pharmacy Staff'),
    'pharmacist', -- All signups start as pharmacist; admin promotes if needed
    false         -- All signups start inactive; admin activates when approved
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ------------------------------------------------------------------------------
-- Table 2: CATEGORIES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.categories (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                text NOT NULL UNIQUE,
  slug                text NOT NULL UNIQUE,
  description         text,
  storage_temperature text DEFAULT 'Room Temperature',
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_categories_updated_at ON public.categories;
CREATE TRIGGER set_categories_updated_at
  BEFORE UPDATE ON public.categories
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 3: BRANDS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.brands (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL UNIQUE,
  manufacturer    text,
  contact_email   text,
  contact_phone   text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_brands_updated_at ON public.brands;
CREATE TRIGGER set_brands_updated_at
  BEFORE UPDATE ON public.brands
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 4: MEDICINES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.medicines (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name                  text NOT NULL,
  generic_name          text,
  category_id           uuid NOT NULL REFERENCES public.categories(id) ON DELETE RESTRICT,
  brand_id              uuid REFERENCES public.brands(id) ON DELETE SET NULL,
  dosage_form           text NOT NULL CHECK (
    dosage_form IN ('Tablet','Capsule','Syrup','Injection','Ointment','Drops','Inhaler','Other')
  ),
  strength              text,
  unit                  text NOT NULL DEFAULT 'Strip',
  hsn_code              text,
  requires_prescription boolean NOT NULL DEFAULT false,
  min_stock_alert       integer NOT NULL DEFAULT 10 CHECK (min_stock_alert >= 0),
  is_active             boolean NOT NULL DEFAULT true,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_medicines_updated_at ON public.medicines;
CREATE TRIGGER set_medicines_updated_at
  BEFORE UPDATE ON public.medicines
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 5: SUPPLIERS
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.suppliers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name             text NOT NULL,
  contact_person   text,
  phone            text NOT NULL,
  email            text,
  address          text,
  gstin            text,
  drug_license_no  text,
  is_active        boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_suppliers_updated_at ON public.suppliers;
CREATE TRIGGER set_suppliers_updated_at
  BEFORE UPDATE ON public.suppliers
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 6: PURCHASES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.purchases (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_no      text NOT NULL,
  supplier_id     uuid NOT NULL REFERENCES public.suppliers(id) ON DELETE RESTRICT,
  purchase_date   date NOT NULL DEFAULT CURRENT_DATE,
  total_amount    numeric(12,2) NOT NULL CHECK (total_amount >= 0),
  tax_amount      numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (tax_amount >= 0),
  discount_amount numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
  net_amount      numeric(12,2) NOT NULL CHECK (net_amount >= 0),
  payment_status  public.payment_status NOT NULL DEFAULT 'paid',
  notes           text,
  created_by      uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_supplier_invoice UNIQUE(supplier_id, invoice_no)
);

DROP TRIGGER IF EXISTS set_purchases_updated_at ON public.purchases;
CREATE TRIGGER set_purchases_updated_at
  BEFORE UPDATE ON public.purchases
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 7: BATCHES
-- Tracks individual medicine lots: expiry, purchase cost, retail price, stock.
-- current_quantity is updated exclusively by secure RPC functions (never directly
-- by clients) to keep stock and stock_movements in sync atomically.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.batches (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  medicine_id      uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  supplier_id      uuid REFERENCES public.suppliers(id) ON DELETE SET NULL,
  batch_no         text NOT NULL,
  mfg_date         date,
  expiry_date      date NOT NULL,
  purchase_cost    numeric(12,2) NOT NULL CHECK (purchase_cost >= 0),
  mrp              numeric(12,2) NOT NULL CHECK (mrp >= 0),
  selling_price    numeric(12,2) NOT NULL CHECK (selling_price >= 0),
  initial_quantity integer NOT NULL CHECK (initial_quantity >= 0),
  current_quantity integer NOT NULL DEFAULT 0 CHECK (current_quantity >= 0),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT check_expiry_after_mfg      CHECK (mfg_date IS NULL OR expiry_date > mfg_date),
  CONSTRAINT check_selling_price_lte_mrp CHECK (selling_price <= mrp),
  CONSTRAINT uq_medicine_batch           UNIQUE(medicine_id, batch_no),
  CONSTRAINT uq_batch_id_medicine        UNIQUE(id, medicine_id) -- Supports composite FK in items tables
);

DROP TRIGGER IF EXISTS set_batches_updated_at ON public.batches;
CREATE TRIGGER set_batches_updated_at
  BEFORE UPDATE ON public.batches
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 8: PURCHASE_ITEMS
-- Line items linking a purchase bill to a specific batch of a medicine.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.purchase_items (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_id uuid NOT NULL REFERENCES public.purchases(id) ON DELETE CASCADE,
  medicine_id uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  batch_id    uuid NOT NULL,
  quantity    integer NOT NULL CHECK (quantity > 0),
  unit_cost   numeric(12,2) NOT NULL CHECK (unit_cost >= 0),
  tax_rate    numeric(5,2) NOT NULL DEFAULT 0.00 CHECK (tax_rate >= 0),
  subtotal    numeric(12,2) NOT NULL CHECK (subtotal >= 0),
  created_at  timestamptz NOT NULL DEFAULT now(),
  -- Composite FK: ensures batch_id actually belongs to medicine_id
  CONSTRAINT fk_purchase_item_batch_medicine
    FOREIGN KEY (batch_id, medicine_id)
    REFERENCES public.batches(id, medicine_id)
    ON DELETE RESTRICT
);

-- ------------------------------------------------------------------------------
-- Table 9: CUSTOMERS
-- Patient / recurring client records. Contains PII — not audited via triggers.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.customers (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name               text NOT NULL,
  phone              text UNIQUE,
  email              text,
  address            text,
  doctor_name        text,
  allergies_or_notes text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_customers_updated_at ON public.customers;
CREATE TRIGGER set_customers_updated_at
  BEFORE UPDATE ON public.customers
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 10: INVOICES
-- Sales receipts generated at the pharmacy counter.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invoices (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_no              text NOT NULL UNIQUE,
  customer_id             uuid REFERENCES public.customers(id) ON DELETE SET NULL,
  total_amount            numeric(12,2) NOT NULL CHECK (total_amount >= 0),
  tax_amount              numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (tax_amount >= 0),
  discount_amount         numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
  net_amount              numeric(12,2) NOT NULL CHECK (net_amount >= 0),
  payment_method          public.payment_method NOT NULL DEFAULT 'cash',
  payment_status          public.payment_status NOT NULL DEFAULT 'paid',
  doctor_prescription_ref text,
  notes                   text,
  created_by              uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at              timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_invoices_updated_at ON public.invoices;
CREATE TRIGGER set_invoices_updated_at
  BEFORE UPDATE ON public.invoices
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 11: INVOICE_ITEMS
-- Line items in a sale invoice. Includes cost snapshot for historical P&L.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invoice_items (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_id            uuid NOT NULL REFERENCES public.invoices(id) ON DELETE CASCADE,
  medicine_id           uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  batch_id              uuid NOT NULL,
  quantity              integer NOT NULL CHECK (quantity > 0),
  unit_price            numeric(12,2) NOT NULL CHECK (unit_price >= 0),
  purchase_cost_at_sale numeric(12,2) NOT NULL CHECK (purchase_cost_at_sale >= 0),
  tax_rate              numeric(5,2) NOT NULL DEFAULT 0.00 CHECK (tax_rate >= 0),
  discount_amount       numeric(12,2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
  subtotal              numeric(12,2) NOT NULL CHECK (subtotal >= 0),
  created_at            timestamptz NOT NULL DEFAULT now(),
  -- Composite FK: ensures batch_id actually belongs to medicine_id
  CONSTRAINT fk_invoice_item_batch_medicine
    FOREIGN KEY (batch_id, medicine_id)
    REFERENCES public.batches(id, medicine_id)
    ON DELETE RESTRICT
);

-- ------------------------------------------------------------------------------
-- Table 12: EXPENSES
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.expenses (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title          text NOT NULL,
  category       text NOT NULL,
  amount         numeric(12,2) NOT NULL CHECK (amount > 0),
  expense_date   date NOT NULL DEFAULT CURRENT_DATE,
  payment_method text NOT NULL DEFAULT 'cash',
  receipt_url    text,
  notes          text,
  created_by     uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS set_expenses_updated_at ON public.expenses;
CREATE TRIGGER set_expenses_updated_at
  BEFORE UPDATE ON public.expenses
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- ------------------------------------------------------------------------------
-- Table 13: STOCK_MOVEMENTS
-- Immutable inventory ledger. Every stock change is permanently recorded here.
-- No UPDATE or DELETE RLS policies exist — rows are append-only by design.
-- This table is itself a complete audit trail; a separate audit trigger is
-- not needed and would create redundant entries.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_movements (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  medicine_id     uuid NOT NULL REFERENCES public.medicines(id) ON DELETE RESTRICT,
  batch_id        uuid NOT NULL,
  movement_type   public.movement_type NOT NULL,
  quantity_change integer NOT NULL CHECK (quantity_change != 0),
  quantity_before integer NOT NULL CHECK (quantity_before >= 0),
  quantity_after  integer NOT NULL CHECK (quantity_after >= 0),
  reference_id    uuid,   -- Points to invoice_id, purchase_id, etc.
  reference_type  text,   -- 'invoice', 'purchase', 'manual_adjustment'
  reason          text,
  created_by      uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- Ledger math integrity: quantity_after MUST equal quantity_before + quantity_change
  CONSTRAINT check_stock_movement_math
    CHECK (quantity_after = quantity_before + quantity_change),
  -- Composite FK: ensures batch_id belongs to medicine_id
  CONSTRAINT fk_stock_movement_batch_medicine
    FOREIGN KEY (batch_id, medicine_id)
    REFERENCES public.batches(id, medicine_id)
    ON DELETE RESTRICT
);

-- ------------------------------------------------------------------------------
-- Table 14: AUDIT_LOGS
-- Immutable administrative activity log. Written ONLY by SECURITY DEFINER triggers.
-- No client-facing INSERT/UPDATE/DELETE RLS policies exist on this table.
-- ip_address and user_agent are populated by application-layer calls in Phase 3+.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
  action     text NOT NULL, -- 'INSERT','UPDATE','DELETE', or custom action names
  table_name text NOT NULL,
  record_id  uuid,
  old_data   jsonb,         -- Row state before the change (NULL for INSERT)
  new_data   jsonb,         -- Row state after the change (NULL for DELETE)
  ip_address text,          -- To be populated by application layer (Phase 3+)
  user_agent text,          -- To be populated by application layer (Phase 3+)
  created_at timestamptz NOT NULL DEFAULT now()
);


-- ==============================================================================
-- 6. INITIAL ADMIN PROVISIONING FUNCTION (NEW in v4)
-- ==============================================================================
-- This function is the ONLY way to create the first admin account.
-- It can only be called from the Supabase SQL Editor by the project owner.
-- Regular authenticated app users (role = authenticated) cannot call it.
--
-- Usage (run in Supabase SQL Editor after the store owner signs up):
--   SELECT public.provision_initial_admin('owner@yourpharmacy.com');
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.provision_initial_admin(p_email text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_user_id     uuid;
  v_admin_count integer;
BEGIN
  -- ── FIX A (new in v5): Acquire an exclusive advisory lock FIRST. ──────────
  -- Without this lock, two simultaneous SQL Editor sessions could both pass
  -- the "no admin exists" check below before either one commits, resulting in
  -- two admins being created. The advisory lock forces them to run one at a
  -- time. pg_advisory_xact_lock is automatically released when the transaction
  -- ends, so there is no manual cleanup needed.
  PERFORM pg_advisory_xact_lock(hashtext('medishop_provision_initial_admin'));
  -- ─────────────────────────────────────────────────────────────────────────

  -- Guard 1: Refuse if any active admin already exists.
  -- Re-checked AFTER acquiring the lock so the result is accurate even
  -- if another session completed provisioning moments earlier.
  -- This makes the function permanently single-use after successful setup.
  SELECT COUNT(*) INTO v_admin_count
  FROM public.profiles
  WHERE role = 'admin' AND is_active = true;

  IF v_admin_count > 0 THEN
    RETURN
      'ERROR: An active admin account already exists. '
      'This function is single-use and has already been applied. '
      'Use the MediShop Staff Management page to manage roles.';
  END IF;

  -- Guard 2: Verify the user has actually signed up through the app.
  SELECT id INTO v_user_id
  FROM auth.users
  WHERE email = lower(trim(p_email));

  IF v_user_id IS NULL THEN
    RETURN
      'ERROR: No registered account found for "' || p_email || '". '
      'The store owner must sign up through the MediShop app first, '
      'then run this command.';
  END IF;

  -- Promote the matched profile to active admin.
  -- The enforce_profile_security trigger allows this because auth.uid() IS NULL
  -- in a SQL Editor (service_role / postgres) session.
  UPDATE public.profiles
  SET
    role      = 'admin',
    is_active = true,
    updated_at = now()
  WHERE id = v_user_id;

  -- Write a permanent audit record of this privileged provisioning action.
  -- session_user captures the Supabase database role (postgres / service_role).
  INSERT INTO public.audit_logs (user_id, action, table_name, record_id, old_data, new_data)
  VALUES (
    v_user_id,
    'INITIAL_ADMIN_PROVISIONED',
    'profiles',
    v_user_id,
    jsonb_build_object('role', 'pharmacist', 'is_active', false),
    jsonb_build_object(
      'role',           'admin',
      'is_active',      true,
      'email',          lower(trim(p_email)),
      'provisioned_by', session_user  -- database role: postgres / service_role
    )
  );

  RETURN
    'SUCCESS: "' || lower(trim(p_email)) || '" is now an active admin. '
    'Log in to MediShop and use the Staff Management page to activate '
    'and assign roles to other staff members.';
END;
$$;

-- Restrict to superuser / service_role only.
-- The Supabase SQL Editor runs as "postgres" (superuser) and can always
-- execute functions regardless of GRANT/REVOKE. This revoke only prevents
-- any authenticated API user from calling this function via PostgREST.
REVOKE EXECUTE ON FUNCTION public.provision_initial_admin(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.provision_initial_admin(text) FROM authenticated;


-- ==============================================================================
-- 7. AUDIT LOGGING TRIGGER FUNCTIONS (NEW in v4)
-- ==============================================================================

-- ── Generic Audit Trigger Function ───────────────────────────────────────────
-- Logs full before/after row snapshots for INSERT, UPDATE, and DELETE operations.
-- Applied to: medicines, purchases, invoices, batches.
--
-- SECURITY DEFINER: Bypasses RLS to write to audit_logs from within the database
-- engine, even though no client-facing INSERT policy exists on audit_logs.
-- SET search_path = '': Prevents search_path hijacking.
-- AFTER trigger: Captures the final committed row state, not an intermediate one.
CREATE OR REPLACE FUNCTION public.audit_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  INSERT INTO public.audit_logs (
    user_id,
    action,
    table_name,
    record_id,
    old_data,
    new_data
  ) VALUES (
    auth.uid(),    -- UUID of the API caller; NULL for service_role / migration scripts
    TG_OP,         -- 'INSERT', 'UPDATE', or 'DELETE'
    TG_TABLE_NAME::text,
    -- For DELETE triggers NEW is NULL; for INSERT triggers OLD is NULL.
    CASE TG_OP WHEN 'DELETE' THEN OLD.id ELSE NEW.id END,
    -- old_data: the complete row as it was BEFORE the change
    CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) ELSE NULL END,
    -- new_data: the complete row as it is AFTER the change
    CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN to_jsonb(NEW) ELSE NULL END
  );
  -- Return value is ignored by the engine for AFTER triggers; use NEW or OLD.
  RETURN COALESCE(NEW, OLD);
END;
$$;

-- Functions with RETURNS TRIGGER cannot be called directly (they require a
-- trigger context), but we revoke explicitly to prevent future confusion.
REVOKE EXECUTE ON FUNCTION public.audit_changes() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.audit_changes() FROM authenticated;


-- ── Profile Security Audit Trigger Function ───────────────────────────────────
-- Logs ONLY role and is_active changes, never PII fields like full_name or phone.
-- This minimises the amount of personal information stored in the audit log
-- while still providing full accountability for all privileged status changes.
CREATE OR REPLACE FUNCTION public.audit_profile_security_changes()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  -- Only write a log entry when role or is_active actually changed.
  -- A simple name or phone update produces no audit record.
  IF (NEW.role IS DISTINCT FROM OLD.role)
  OR (NEW.is_active IS DISTINCT FROM OLD.is_active)
  THEN
    INSERT INTO public.audit_logs (
      user_id,
      action,
      table_name,
      record_id,
      old_data,
      new_data
    ) VALUES (
      auth.uid(),  -- Who performed the change (admin UUID, or NULL for service_role)
      'ROLE_OR_STATUS_CHANGE',
      'profiles',
      NEW.id,      -- Which staff profile was changed
      -- Log only the security-relevant fields, not the full profile row (avoids PII)
      jsonb_build_object(
        'role',      OLD.role,
        'is_active', OLD.is_active
      ),
      jsonb_build_object(
        'role',       NEW.role,
        'is_active',  NEW.is_active,
        'changed_by', auth.uid()  -- Explicit: who made this privileged change
      )
    );
  END IF;
  RETURN NEW;
END;
$$;

REVOKE EXECUTE ON FUNCTION public.audit_profile_security_changes() FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.audit_profile_security_changes() FROM authenticated;


-- ==============================================================================
-- 8. PERFORMANCE & FEFO INDEXES
-- ==============================================================================

-- Medicines
CREATE INDEX IF NOT EXISTS idx_medicines_category  ON public.medicines(category_id);
CREATE INDEX IF NOT EXISTS idx_medicines_brand     ON public.medicines(brand_id);
CREATE INDEX IF NOT EXISTS idx_medicines_name      ON public.medicines(name);
CREATE INDEX IF NOT EXISTS idx_medicines_generic   ON public.medicines(generic_name);
CREATE INDEX IF NOT EXISTS idx_medicines_low_stock ON public.medicines(min_stock_alert)
  WHERE is_active = true;

-- Batches — FEFO (First Expiry, First Out) ordering for dispensing
CREATE INDEX IF NOT EXISTS idx_batches_fefo    ON public.batches(medicine_id, expiry_date ASC, current_quantity)
  WHERE current_quantity > 0;
CREATE INDEX IF NOT EXISTS idx_batches_expiry  ON public.batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_batches_supplier ON public.batches(supplier_id);

-- Purchases
CREATE INDEX IF NOT EXISTS idx_purchases_supplier      ON public.purchases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchases_date          ON public.purchases(purchase_date DESC);
CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON public.purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_medicine ON public.purchase_items(medicine_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_batch    ON public.purchase_items(batch_id);

-- Invoices & Sales Reporting
CREATE INDEX IF NOT EXISTS idx_invoices_customer      ON public.invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_created_at    ON public.invoices(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoices_no            ON public.invoices(invoice_no);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice  ON public.invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_medicine ON public.invoice_items(medicine_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_batch    ON public.invoice_items(batch_id);

-- Stock Movements & Audit
CREATE INDEX IF NOT EXISTS idx_stock_movements_medicine ON public.stock_movements(medicine_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_stock_movements_batch    ON public.stock_movements(batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_ref      ON public.stock_movements(reference_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user          ON public.audit_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_table         ON public.audit_logs(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_expenses_date            ON public.expenses(expense_date DESC);


-- ==============================================================================
-- 9. ROW LEVEL SECURITY — Enable on all 14 tables
-- ==============================================================================
ALTER TABLE public.profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.brands          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.medicines       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.suppliers       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchases       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_items  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batches         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.customers       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoice_items   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.expenses        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs      ENABLE ROW LEVEL SECURITY;


-- ==============================================================================
-- 10. RLS POLICIES (Idempotent — DROP IF EXISTS before CREATE)
-- ==============================================================================

-- ── PROFILES ──────────────────────────────────────────────────────────────────
-- Staff can view their own profile; all active staff can view all profiles.
DROP POLICY IF EXISTS "profiles_select_own_or_staff" ON public.profiles;
CREATE POLICY "profiles_select_own_or_staff"
  ON public.profiles FOR SELECT TO authenticated
  USING (id = auth.uid() OR public.is_staff());

-- Any authenticated user can update their own profile (name, phone, etc.).
-- The enforce_profile_security BEFORE trigger then blocks role/is_active
-- changes for non-admins.
DROP POLICY IF EXISTS "profiles_update_self" ON public.profiles;
CREATE POLICY "profiles_update_self"
  ON public.profiles FOR UPDATE TO authenticated
  USING   (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- Admins have full access to all profile rows.
DROP POLICY IF EXISTS "profiles_admin_all" ON public.profiles;
CREATE POLICY "profiles_admin_all"
  ON public.profiles FOR ALL TO authenticated
  USING   (public.is_admin())
  WITH CHECK (public.is_admin());

-- ── CATEGORIES & BRANDS ───────────────────────────────────────────────────────
DROP POLICY IF EXISTS "categories_select_staff"  ON public.categories;
CREATE POLICY "categories_select_staff"
  ON public.categories FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "categories_admin_modify"  ON public.categories;
CREATE POLICY "categories_admin_modify"
  ON public.categories FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "brands_select_staff"      ON public.brands;
CREATE POLICY "brands_select_staff"
  ON public.brands FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "brands_admin_modify"      ON public.brands;
CREATE POLICY "brands_admin_modify"
  ON public.brands FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── MEDICINES ─────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS "medicines_select_staff"   ON public.medicines;
CREATE POLICY "medicines_select_staff"
  ON public.medicines FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "medicines_admin_all"      ON public.medicines;
CREATE POLICY "medicines_admin_all"
  ON public.medicines FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── SUPPLIERS ─────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS "suppliers_select_staff"   ON public.suppliers;
CREATE POLICY "suppliers_select_staff"
  ON public.suppliers FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "suppliers_admin_modify"   ON public.suppliers;
CREATE POLICY "suppliers_admin_modify"
  ON public.suppliers FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── BATCHES ───────────────────────────────────────────────────────────────────
-- Direct client updates are admin-only.
-- Pharmacist stock updates happen exclusively via secure RPC functions in
-- Phase 3 (purchase_in_rpc) and Phase 4 (checkout_invoice_rpc), which run
-- as SECURITY DEFINER and bypass RLS to update batches programmatically.
DROP POLICY IF EXISTS "batches_select_staff"     ON public.batches;
CREATE POLICY "batches_select_staff"
  ON public.batches FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "batches_admin_all"        ON public.batches;
CREATE POLICY "batches_admin_all"
  ON public.batches FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── PURCHASES & PURCHASE_ITEMS ────────────────────────────────────────────────
-- Direct REST insertion is restricted to admin.
-- Staff create purchases atomically via a secure RPC function (Phase 3).
DROP POLICY IF EXISTS "purchases_select_staff"       ON public.purchases;
CREATE POLICY "purchases_select_staff"
  ON public.purchases FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "purchases_admin_all"          ON public.purchases;
CREATE POLICY "purchases_admin_all"
  ON public.purchases FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "purchase_items_select_staff"  ON public.purchase_items;
CREATE POLICY "purchase_items_select_staff"
  ON public.purchase_items FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "purchase_items_admin_all"     ON public.purchase_items;
CREATE POLICY "purchase_items_admin_all"
  ON public.purchase_items FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── CUSTOMERS ─────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS "customers_select_staff"   ON public.customers;
CREATE POLICY "customers_select_staff"
  ON public.customers FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "customers_insert_staff"   ON public.customers;
CREATE POLICY "customers_insert_staff"
  ON public.customers FOR INSERT TO authenticated
  WITH CHECK (public.is_staff());

DROP POLICY IF EXISTS "customers_update_staff"   ON public.customers;
CREATE POLICY "customers_update_staff"
  ON public.customers FOR UPDATE TO authenticated
  USING (public.is_staff()) WITH CHECK (public.is_staff());

DROP POLICY IF EXISTS "customers_admin_delete"   ON public.customers;
CREATE POLICY "customers_admin_delete"
  ON public.customers FOR DELETE TO authenticated
  USING (public.is_admin());

-- ── INVOICES & INVOICE_ITEMS ──────────────────────────────────────────────────
-- Direct REST insertion is restricted to admin to prevent forged line items,
-- price overrides, or stock desynchronization.
-- Checkout creates invoices + items + stock update atomically via RPC (Phase 4).
DROP POLICY IF EXISTS "invoices_select_staff"       ON public.invoices;
CREATE POLICY "invoices_select_staff"
  ON public.invoices FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "invoices_admin_all"          ON public.invoices;
CREATE POLICY "invoices_admin_all"
  ON public.invoices FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "invoice_items_select_staff"  ON public.invoice_items;
CREATE POLICY "invoice_items_select_staff"
  ON public.invoice_items FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "invoice_items_admin_all"     ON public.invoice_items;
CREATE POLICY "invoice_items_admin_all"
  ON public.invoice_items FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── EXPENSES ──────────────────────────────────────────────────────────────────
DROP POLICY IF EXISTS "expenses_select_staff"    ON public.expenses;
CREATE POLICY "expenses_select_staff"
  ON public.expenses FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "expenses_insert_staff"    ON public.expenses;
CREATE POLICY "expenses_insert_staff"
  ON public.expenses FOR INSERT TO authenticated
  WITH CHECK (public.is_staff() AND (created_by IS NULL OR created_by = auth.uid()));

DROP POLICY IF EXISTS "expenses_admin_modify"    ON public.expenses;
CREATE POLICY "expenses_admin_modify"
  ON public.expenses FOR ALL TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- ── STOCK_MOVEMENTS (Immutable Inventory Ledger) ──────────────────────────────
-- SELECT: any active staff. INSERT: admin only (or SECURITY DEFINER RPC functions).
-- No UPDATE or DELETE policies: rows are permanently immutable by design.
DROP POLICY IF EXISTS "stock_movements_select_staff"  ON public.stock_movements;
CREATE POLICY "stock_movements_select_staff"
  ON public.stock_movements FOR SELECT TO authenticated USING (public.is_staff());

DROP POLICY IF EXISTS "stock_movements_admin_insert"  ON public.stock_movements;
CREATE POLICY "stock_movements_admin_insert"
  ON public.stock_movements FOR INSERT TO authenticated
  WITH CHECK (public.is_admin());

-- ── AUDIT_LOGS (Admin-readable only; trigger-writable only) ──────────────────
-- SELECT: admin only.
-- No INSERT/UPDATE/DELETE policies for any client role.
-- Only SECURITY DEFINER trigger functions (audit_changes, audit_profile_security_changes,
-- and provision_initial_admin) can write to this table — making it tamper-proof.
DROP POLICY IF EXISTS "audit_logs_select_admin"  ON public.audit_logs;
CREATE POLICY "audit_logs_select_admin"
  ON public.audit_logs FOR SELECT TO authenticated
  USING (public.is_admin());


-- ==============================================================================
-- 11. AUDIT TRIGGERS (NEW in v4)
-- Placed after all table and policy definitions to guarantee correct dependency
-- order. All audit triggers are AFTER triggers so they capture the final state.
-- ==============================================================================

-- Profiles: log role/is_active changes ONLY (not full row — avoids PII logging)
DROP TRIGGER IF EXISTS audit_profiles_security ON public.profiles;
CREATE TRIGGER audit_profiles_security
  AFTER UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.audit_profile_security_changes();

-- Medicines: log every add, edit, or delete of a medicine record
DROP TRIGGER IF EXISTS audit_medicines ON public.medicines;
CREATE TRIGGER audit_medicines
  AFTER INSERT OR UPDATE OR DELETE ON public.medicines
  FOR EACH ROW EXECUTE FUNCTION public.audit_changes();

-- Purchases: log every add, edit, or delete of a purchase bill header
DROP TRIGGER IF EXISTS audit_purchases ON public.purchases;
CREATE TRIGGER audit_purchases
  AFTER INSERT OR UPDATE OR DELETE ON public.purchases
  FOR EACH ROW EXECUTE FUNCTION public.audit_changes();

-- Invoices: log every add, edit, or delete of a sales invoice header
DROP TRIGGER IF EXISTS audit_invoices ON public.invoices;
CREATE TRIGGER audit_invoices
  AFTER INSERT OR UPDATE OR DELETE ON public.invoices
  FOR EACH ROW EXECUTE FUNCTION public.audit_changes();

-- Batches: log every new batch addition and every update.
-- Captures full before/after state of stock quantity changes.
-- When Phase 3/4 RPC functions update current_quantity, this trigger fires
-- automatically and records auth.uid() of the calling staff member.
DROP TRIGGER IF EXISTS audit_batches ON public.batches;
CREATE TRIGGER audit_batches
  AFTER INSERT OR UPDATE ON public.batches
  FOR EACH ROW EXECUTE FUNCTION public.audit_changes();


-- ==============================================================================
-- END OF MIGRATION: 20261027000004_initial_schema_v4_audit_secure.sql
-- ==============================================================================
-- REMAINING CONCERNS (for manual review / future phases):
--
-- 1. PARTIAL AUDIT COVERAGE: Expenses, suppliers, categories, and brands are not
--    yet audited. Add triggers for these in a future migration if compliance
--    requirements demand it.
--
-- 2. CUSTOMER PII IN AUDIT: audit_logs for invoices includes customer_id (a UUID
--    foreign key, not the name/phone). Full customer history is not logged.
--    If HIPAA/DPDP compliance is required, a separate privacy-scoped audit
--    strategy should be designed.
--
-- 3. AUDIT LOG RETENTION: The audit_logs table will grow indefinitely. Plan a
--    log rotation / archiving strategy before going to production.
--
-- 4. PHARMACIST CHECKOUT BLOCKED UNTIL PHASE 4: Currently only admins can INSERT
--    invoices directly. Pharmacists depend on the Phase 4 checkout_invoice_rpc
--    SECURITY DEFINER function to create sales. Do not go live for pharmacist
--    sales until that RPC function is built, tested, and deployed.
--
-- ITEMS RESOLVED IN v5:
--   ✓ Last-admin lockout: enforce_profile_security() now blocks demotion/
--     deactivation of the sole remaining active admin (FIX B).
--   ✓ provision_initial_admin() race condition: pg_advisory_xact_lock prevents
--     simultaneous calls from both completing successfully (FIX A).
-- ==============================================================================
