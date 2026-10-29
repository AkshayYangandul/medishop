-- ==============================================================================
-- MediShop: Medical Shop Management System
-- Database Schema for MySQL 8.0 (InnoDB)
-- Converted from: supabase/migrations/20261027000005_initial_schema_v5_review.sql
-- ==============================================================================
--
-- ARCHITECTURAL DESIGN & MIGRATION SPECIFICATIONS:
--
-- 1. DATABASE CONTEXT AGNOSTIC:
--    This file contains NO hardcoded 'USE <dbname>;' statements.
--    Target database is determined exclusively by the database connection URL
--    or the calling CLI runner, ensuring safe execution in disposable test environments.
--
-- 2. AUTHENTICATION & CREDENTIALS:
--    Supabase's internal 'auth.users' table is replaced by native columns on
--    'profiles' (email, password_hash). Fast, direct indexing on email without
--    redundant cross-schema joins. Passwords must be hashed using bcrypt (cost 12)
--    by the application layer before insertion.
--
-- 3. ROW LEVEL SECURITY (RLS) REPLACEMENT:
--    MySQL 8.0 does not support PostgreSQL RLS. Access control (is_admin, is_staff)
--    is enforced at the FastAPI application layer via dependency injection
--    (Depends(require_active_admin), Depends(require_active_staff)).
--
-- 4. DATABASE-LEVEL IMMUTABILITY TRIGGERS:
--    - 'stock_movements': BEFORE UPDATE and BEFORE DELETE triggers block modification.
--    - 'audit_logs': BEFORE UPDATE and BEFORE DELETE triggers block modification.
--    (Note on Last-Active-Admin Protection: In MySQL 8.0, querying 'profiles' from a row-level
--    trigger on 'profiles' risks MySQL Error 1442 and cannot prevent concurrent MVCC race conditions.
--    Therefore, last-active-admin protection is strictly and safely enforced at the FastAPI
--    application layer via the serialized named-lock protocol 'medishop_admin_role_mutex').
--
-- 5. BUSINESS RULES & CONSTRAINTS PRESERVED:
--    - Batches: selling_price <= mrp (CHECK constraint check_selling_price_lte_mrp).
--    - Batches: expiry_date > mfg_date (CHECK constraint check_expiry_after_mfg).
--    - Batches: UNIQUE (id, medicine_id) supporting child composite foreign keys.
--    - Purchase Items & Invoice Items: Composite FK (batch_id, medicine_id) -> batches(id, medicine_id).
--    - Stock Movements: Ledger math check (quantity_after = quantity_before + quantity_change).
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Table 1: PROFILES
-- User accounts with authentication credentials and role authorization.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profiles (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role ENUM('admin', 'pharmacist') NOT NULL DEFAULT 'pharmacist',
    phone VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_profiles_email UNIQUE (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 2: CATEGORIES
-- Drug categories / therapeutic classes.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    storage_temperature VARCHAR(100) DEFAULT 'Room Temperature',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_categories_name UNIQUE (name),
    CONSTRAINT uq_categories_slug UNIQUE (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 3: BRANDS
-- Pharmaceutical manufacturers / pharmaceutical brands.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS brands (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_brands_name UNIQUE (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 4: MEDICINES
-- Core catalog of pharmaceutical products.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS medicines (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    category_id CHAR(36) NOT NULL,
    brand_id CHAR(36),
    dosage_form ENUM('Tablet', 'Capsule', 'Syrup', 'Injection', 'Ointment', 'Drops', 'Inhaler', 'Other') NOT NULL,
    strength VARCHAR(100),
    unit VARCHAR(50) NOT NULL DEFAULT 'Strip',
    hsn_code VARCHAR(50),
    requires_prescription BOOLEAN NOT NULL DEFAULT FALSE,
    min_stock_alert INT NOT NULL DEFAULT 10,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_medicines_min_stock_alert CHECK (min_stock_alert >= 0),
    CONSTRAINT fk_medicines_category FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE RESTRICT,
    CONSTRAINT fk_medicines_brand FOREIGN KEY (brand_id) REFERENCES brands (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 5: SUPPLIERS
-- Wholesale vendors and pharmaceutical distributors.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    contact_person VARCHAR(255),
    phone VARCHAR(50) NOT NULL,
    email VARCHAR(255),
    address TEXT,
    gstin VARCHAR(50),
    drug_license_no VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 6: PURCHASES
-- Inward stock procurement purchase orders and supplier bills.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchases (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    invoice_no VARCHAR(100) NOT NULL,
    supplier_id CHAR(36) NOT NULL,
    purchase_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    total_amount DECIMAL(12, 2) NOT NULL,
    tax_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    net_amount DECIMAL(12, 2) NOT NULL,
    payment_status ENUM('paid', 'pending', 'partial', 'cancelled') NOT NULL DEFAULT 'paid',
    notes TEXT,
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_purchases_total_amount CHECK (total_amount >= 0),
    CONSTRAINT check_purchases_tax_amount CHECK (tax_amount >= 0),
    CONSTRAINT check_purchases_discount_amount CHECK (discount_amount >= 0),
    CONSTRAINT check_purchases_net_amount CHECK (net_amount >= 0),
    CONSTRAINT uq_supplier_invoice UNIQUE (supplier_id, invoice_no),
    CONSTRAINT fk_purchases_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchases_created_by FOREIGN KEY (created_by) REFERENCES profiles (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 7: BATCHES
-- Specific manufacturing lots of medicines with expiration and pricing.
-- Supports composite foreign keys via (id, medicine_id).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS batches (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    medicine_id CHAR(36) NOT NULL,
    supplier_id CHAR(36),
    batch_no VARCHAR(100) NOT NULL,
    mfg_date DATE,
    expiry_date DATE NOT NULL,
    purchase_cost DECIMAL(12, 2) NOT NULL,
    mrp DECIMAL(12, 2) NOT NULL,
    selling_price DECIMAL(12, 2) NOT NULL,
    initial_quantity INT NOT NULL,
    current_quantity INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_batches_purchase_cost CHECK (purchase_cost >= 0),
    CONSTRAINT check_batches_mrp CHECK (mrp >= 0),
    CONSTRAINT check_batches_selling_price CHECK (selling_price >= 0),
    CONSTRAINT check_batches_initial_quantity CHECK (initial_quantity >= 0),
    CONSTRAINT check_batches_current_quantity CHECK (current_quantity >= 0),
    CONSTRAINT check_expiry_after_mfg CHECK (mfg_date IS NULL OR expiry_date > mfg_date),
    CONSTRAINT check_selling_price_lte_mrp CHECK (selling_price <= mrp),
    CONSTRAINT uq_medicine_batch UNIQUE (medicine_id, batch_no),
    CONSTRAINT uq_batch_id_medicine UNIQUE (id, medicine_id),
    CONSTRAINT fk_batches_medicine FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE RESTRICT,
    CONSTRAINT fk_batches_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 8: PURCHASE_ITEMS
-- Line items in a purchase bill. Links directly to a batch and medicine.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS purchase_items (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    purchase_id CHAR(36) NOT NULL,
    medicine_id CHAR(36) NOT NULL,
    batch_id CHAR(36) NOT NULL,
    quantity INT NOT NULL,
    unit_cost DECIMAL(12, 2) NOT NULL,
    tax_rate DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    subtotal DECIMAL(12, 2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_purchase_items_quantity CHECK (quantity > 0),
    CONSTRAINT check_purchase_items_unit_cost CHECK (unit_cost >= 0),
    CONSTRAINT check_purchase_items_tax_rate CHECK (tax_rate >= 0),
    CONSTRAINT check_purchase_items_subtotal CHECK (subtotal >= 0),
    CONSTRAINT fk_purchase_items_purchase FOREIGN KEY (purchase_id) REFERENCES purchases (id) ON DELETE CASCADE,
    CONSTRAINT fk_purchase_items_medicine FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE RESTRICT,
    CONSTRAINT fk_purchase_item_batch_medicine FOREIGN KEY (batch_id, medicine_id) REFERENCES batches (id, medicine_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 9: CUSTOMERS
-- Patient and recurring retail customer records.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS customers (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    doctor_name VARCHAR(255),
    allergies_or_notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_customers_phone UNIQUE (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 10: INVOICES
-- Counter sales receipts issued to customers.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoices (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    invoice_no VARCHAR(100) NOT NULL,
    customer_id CHAR(36),
    total_amount DECIMAL(12, 2) NOT NULL,
    tax_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    net_amount DECIMAL(12, 2) NOT NULL,
    payment_method ENUM('cash', 'upi', 'card', 'credit', 'split') NOT NULL DEFAULT 'cash',
    payment_status ENUM('paid', 'pending', 'partial', 'cancelled') NOT NULL DEFAULT 'paid',
    doctor_prescription_ref VARCHAR(255),
    notes TEXT,
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_invoices_total_amount CHECK (total_amount >= 0),
    CONSTRAINT check_invoices_tax_amount CHECK (tax_amount >= 0),
    CONSTRAINT check_invoices_discount_amount CHECK (discount_amount >= 0),
    CONSTRAINT check_invoices_net_amount CHECK (net_amount >= 0),
    CONSTRAINT uq_invoices_invoice_no UNIQUE (invoice_no),
    CONSTRAINT fk_invoices_customer FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE SET NULL,
    CONSTRAINT fk_invoices_created_by FOREIGN KEY (created_by) REFERENCES profiles (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 11: INVOICE_ITEMS
-- Dispensed medicines on an invoice, capturing cost-at-sale for profit & loss.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoice_items (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    invoice_id CHAR(36) NOT NULL,
    medicine_id CHAR(36) NOT NULL,
    batch_id CHAR(36) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    purchase_cost_at_sale DECIMAL(12, 2) NOT NULL,
    tax_rate DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    discount_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    subtotal DECIMAL(12, 2) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_invoice_items_quantity CHECK (quantity > 0),
    CONSTRAINT check_invoice_items_unit_price CHECK (unit_price >= 0),
    CONSTRAINT check_invoice_items_cost_at_sale CHECK (purchase_cost_at_sale >= 0),
    CONSTRAINT check_invoice_items_tax_rate CHECK (tax_rate >= 0),
    CONSTRAINT check_invoice_items_discount CHECK (discount_amount >= 0),
    CONSTRAINT check_invoice_items_subtotal CHECK (subtotal >= 0),
    CONSTRAINT fk_invoice_items_invoice FOREIGN KEY (invoice_id) REFERENCES invoices (id) ON DELETE CASCADE,
    CONSTRAINT fk_invoice_items_medicine FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE RESTRICT,
    CONSTRAINT fk_invoice_item_batch_medicine FOREIGN KEY (batch_id, medicine_id) REFERENCES batches (id, medicine_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 12: EXPENSES
-- Operating expenses (store utilities, rent, supplies, etc.).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS expenses (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    expense_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    payment_method VARCHAR(50) NOT NULL DEFAULT 'cash',
    receipt_url TEXT,
    notes TEXT,
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_expenses_amount CHECK (amount > 0),
    CONSTRAINT fk_expenses_created_by FOREIGN KEY (created_by) REFERENCES profiles (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 13: STOCK_MOVEMENTS
-- Immutable inventory ledger tracking every stock addition and deduction.
-- Math integrity: quantity_after = quantity_before + quantity_change.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock_movements (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    medicine_id CHAR(36) NOT NULL,
    batch_id CHAR(36) NOT NULL,
    movement_type ENUM(
        'purchase_in',
        'sale_out',
        'return_in',
        'return_to_supplier',
        'expired_disposal',
        'damaged_write_off',
        'inventory_adjustment'
    ) NOT NULL,
    quantity_change INT NOT NULL,
    quantity_before INT NOT NULL,
    quantity_after INT NOT NULL,
    reference_id CHAR(36),
    reference_type VARCHAR(50),
    reason TEXT,
    created_by CHAR(36),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT check_stock_movement_qty_change CHECK (quantity_change != 0),
    CONSTRAINT check_stock_movement_qty_before CHECK (quantity_before >= 0),
    CONSTRAINT check_stock_movement_qty_after CHECK (quantity_after >= 0),
    CONSTRAINT check_stock_movement_math CHECK (quantity_after = quantity_before + quantity_change),
    CONSTRAINT fk_stock_movements_medicine FOREIGN KEY (medicine_id) REFERENCES medicines (id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movement_batch_medicine FOREIGN KEY (batch_id, medicine_id) REFERENCES batches (id, medicine_id) ON DELETE RESTRICT,
    CONSTRAINT fk_stock_movements_created_by FOREIGN KEY (created_by) REFERENCES profiles (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------------------------
-- Table 14: AUDIT_LOGS
-- Immutable administrative audit trail for sensitive changes.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id CHAR(36) NOT NULL DEFAULT (UUID()),
    user_id CHAR(36),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100) NOT NULL,
    record_id CHAR(36),
    old_data JSON,
    new_data JSON,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES profiles (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ==============================================================================
-- PERFORMANCE & COMPLIANCE INDEXES
-- Note: MySQL does not support partial/filtered indexes (WHERE clause on index).
-- Standard composite indexes are used instead.
-- ==============================================================================

-- Medicines Indexes
CREATE INDEX idx_medicines_category ON medicines (category_id);
CREATE INDEX idx_medicines_brand ON medicines (brand_id);
CREATE INDEX idx_medicines_name ON medicines (name);
CREATE INDEX idx_medicines_generic ON medicines (generic_name);
-- Converted from PostgreSQL partial index (WHERE is_active = true)
CREATE INDEX idx_medicines_active_stock ON medicines (is_active, min_stock_alert);

-- Batches Indexes (FEFO: First Expiry, First Out)
-- Converted from PostgreSQL partial index (WHERE current_quantity > 0)
CREATE INDEX idx_batches_fefo ON batches (medicine_id, expiry_date ASC, current_quantity);
CREATE INDEX idx_batches_expiry ON batches (expiry_date);
CREATE INDEX idx_batches_supplier ON batches (supplier_id);

-- Purchases & Purchase Items Indexes
CREATE INDEX idx_purchases_supplier ON purchases (supplier_id);
CREATE INDEX idx_purchases_date ON purchases (purchase_date DESC);
CREATE INDEX idx_purchase_items_purchase ON purchase_items (purchase_id);
CREATE INDEX idx_purchase_items_medicine ON purchase_items (medicine_id);
CREATE INDEX idx_purchase_items_batch ON purchase_items (batch_id);

-- Invoices & Sales Reporting Indexes
CREATE INDEX idx_invoices_customer ON invoices (customer_id);
CREATE INDEX idx_invoices_created_at ON invoices (created_at DESC);
CREATE INDEX idx_invoices_no ON invoices (invoice_no);
CREATE INDEX idx_invoice_items_invoice ON invoice_items (invoice_id);
CREATE INDEX idx_invoice_items_medicine ON invoice_items (medicine_id);
CREATE INDEX idx_invoice_items_batch ON invoice_items (batch_id);

-- Stock Movements, Expenses & Audit Logs Indexes
CREATE INDEX idx_stock_movements_medicine ON stock_movements (medicine_id, created_at DESC);
CREATE INDEX idx_stock_movements_batch ON stock_movements (batch_id);
CREATE INDEX idx_stock_movements_ref ON stock_movements (reference_id);
CREATE INDEX idx_expenses_date ON expenses (expense_date DESC);
CREATE INDEX idx_audit_logs_user ON audit_logs (user_id, created_at DESC);
CREATE INDEX idx_audit_logs_table ON audit_logs (table_name, record_id);

-- ==============================================================================
-- DATABASE-LEVEL DEFENSE-IN-DEPTH TRIGGERS
-- Note: Standard DELIMITER syntax is included for MySQL CLI clients.
-- ==============================================================================

DELIMITER $$

-- 1. Prevent UPDATE on stock_movements (Ledger Immutability)
CREATE TRIGGER trg_stock_movements_no_update
BEFORE UPDATE ON stock_movements
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Stock movement records are immutable and cannot be updated.';
END$$

-- 2. Prevent DELETE on stock_movements (Ledger Immutability)
CREATE TRIGGER trg_stock_movements_no_delete
BEFORE DELETE ON stock_movements
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Stock movement records are immutable and cannot be deleted.';
END$$

-- 3. Prevent UPDATE on audit_logs (Audit Trail Immutability)
CREATE TRIGGER trg_audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit log records are immutable and cannot be updated.';
END$$

-- 4. Prevent DELETE on audit_logs (Audit Trail Immutability)
CREATE TRIGGER trg_audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit log records are immutable and cannot be deleted.';
END$$

DELIMITER ;

-- ==============================================================================
-- APPLICATION-LEVEL SECURITY ARCHITECTURE NOTE:
-- Last-Active-Admin Protection:
-- In MySQL 8.0, querying the 'profiles' table from a BEFORE UPDATE trigger on 'profiles'
-- risks MySQL Error 1442 (mutating-table restriction in stored programs) and cannot
-- resolve concurrent MVCC race conditions under REPEATABLE READ isolation.
-- Consequently, last-active-admin protection is strictly implemented at the FastAPI
-- application layer using the serialized named-lock protocol 'medishop_admin_role_mutex'.
-- Every status/role change executes inside this lock with SELECT ... FOR UPDATE,
-- guaranteeing that the system can never be left without an active administrator.
-- ==============================================================================
