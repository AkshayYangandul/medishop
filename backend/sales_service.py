"""
MediShop Sales, Purchases, Inventory Movements, Customers, Suppliers, Expenses & Reporting
========================================================================================
Comprehensive business services for counter sales (POS), procurement (inward purchases),
inventory ledgering (immutable stock_movements), customer records, supplier accounts,
operating expenses, and dashboard analytics.
"""

import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status


# ---------------------------------------------------------------------------
# Suppliers Service
# ---------------------------------------------------------------------------

def supplier_list(engine: Engine, search: str = "") -> List[Dict[str, Any]]:
    """Returns all suppliers, optionally filtered by name, phone, or GSTIN."""
    try:
        with engine.begin() as conn:
            query = (
                "SELECT id, name, contact_person, phone, email, address, "
                "gstin, drug_license_no, is_active, created_at, updated_at "
                "FROM suppliers "
            )
            params: Dict[str, Any] = {}
            if search.strip():
                query += (
                    "WHERE name LIKE :search OR phone LIKE :search "
                    "OR gstin LIKE :search OR contact_person LIKE :search "
                )
                params["search"] = f"%{search.strip()}%"
            query += "ORDER BY name ASC"

            rows = conn.execute(text(query), params).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing suppliers.",
        ) from exc


def supplier_get(engine: Engine, supplier_id: str) -> Dict[str, Any]:
    """Retrieves a single supplier by ID."""
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT id, name, contact_person, phone, email, address, "
                    "gstin, drug_license_no, is_active, created_at, updated_at "
                    "FROM suppliers WHERE id = :id"
                ),
                {"id": supplier_id},
            ).mappings().first()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found.",
                )
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching supplier details.",
        ) from exc


def supplier_create(engine: Engine, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new supplier."""
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supplier name is required.",
        )
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supplier phone number is required.",
        )

    supplier_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO suppliers "
                    "(id, name, contact_person, phone, email, address, gstin, drug_license_no, is_active) "
                    "VALUES (:id, :name, :contact_person, :phone, :email, :address, :gstin, :drug_license_no, :is_active)"
                ),
                {
                    "id": supplier_id,
                    "name": name,
                    "contact_person": payload.get("contact_person"),
                    "phone": phone,
                    "email": payload.get("email"),
                    "address": payload.get("address"),
                    "gstin": payload.get("gstin"),
                    "drug_license_no": payload.get("drug_license_no"),
                    "is_active": bool(payload.get("is_active") if "is_active" in payload else True),
                },
            )

            row = conn.execute(
                text(
                    "SELECT id, name, contact_person, phone, email, address, "
                    "gstin, drug_license_no, is_active, created_at, updated_at "
                    "FROM suppliers WHERE id = :id"
                ),
                {"id": supplier_id},
            ).mappings().first()
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating supplier.",
        ) from exc


def supplier_update(engine: Engine, supplier_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Partially updates a supplier."""
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM suppliers WHERE id = :id"),
                {"id": supplier_id},
            ).first()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found.",
                )

            updates: Dict[str, Any] = {}
            for field in ["name", "contact_person", "phone", "email", "address", "gstin", "drug_license_no"]:
                if field in payload and payload[field] is not None:
                    updates[field] = str(payload[field]).strip()
            if "is_active" in payload and payload["is_active"] is not None:
                updates["is_active"] = bool(payload["is_active"])

            if "name" in updates and not updates["name"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Supplier name cannot be empty.",
                )
            if "phone" in updates and not updates["phone"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Supplier phone cannot be empty.",
                )

            if updates:
                set_clause = ", ".join(f"{col} = :{col}" for col in updates)
                conn.execute(
                    text(f"UPDATE suppliers SET {set_clause} WHERE id = :id"),
                    {**updates, "id": supplier_id},
                )

            row = conn.execute(
                text(
                    "SELECT id, name, contact_person, phone, email, address, "
                    "gstin, drug_license_no, is_active, created_at, updated_at "
                    "FROM suppliers WHERE id = :id"
                ),
                {"id": supplier_id},
            ).mappings().first()
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating supplier.",
        ) from exc


def supplier_delete(engine: Engine, supplier_id: str) -> Dict[str, Any]:
    """Deletes a supplier if not referenced in batches or purchases."""
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM suppliers WHERE id = :id"),
                {"id": supplier_id},
            ).first()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Supplier not found.",
                )

            # Check references in purchases
            ref_purchases = conn.execute(
                text("SELECT id FROM purchases WHERE supplier_id = :id LIMIT 1"),
                {"id": supplier_id},
            ).first()
            if ref_purchases:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete supplier: referenced by purchase records.",
                )

            conn.execute(
                text("DELETE FROM suppliers WHERE id = :id"),
                {"id": supplier_id},
            )
            return {"id": supplier_id, "deleted": True}
    except HTTPException:
        raise
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete supplier: active references exist in the database.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting supplier.",
        ) from exc


# ---------------------------------------------------------------------------
# Customers Service
# ---------------------------------------------------------------------------

def customer_list(engine: Engine, search: str = "") -> List[Dict[str, Any]]:
    """Returns all customer profiles, optionally filtered by search."""
    try:
        with engine.begin() as conn:
            query = (
                "SELECT id, name, phone, email, address, doctor_name, "
                "allergies_or_notes, created_at, updated_at "
                "FROM customers "
            )
            params: Dict[str, Any] = {}
            if search.strip():
                query += "WHERE name LIKE :search OR phone LIKE :search OR email LIKE :search "
                params["search"] = f"%{search.strip()}%"
            query += "ORDER BY name ASC"

            rows = conn.execute(text(query), params).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing customers.",
        ) from exc


def customer_get(engine: Engine, customer_id: str) -> Dict[str, Any]:
    """Retrieves a single customer by ID."""
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT id, name, phone, email, address, doctor_name, "
                    "allergies_or_notes, created_at, updated_at "
                    "FROM customers WHERE id = :id"
                ),
                {"id": customer_id},
            ).mappings().first()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found.",
                )
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching customer details.",
        ) from exc


def customer_create(engine: Engine, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new customer."""
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Customer name is required.",
        )
    phone = str(payload.get("phone") or "").strip() or None

    customer_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            if phone:
                existing_phone = conn.execute(
                    text("SELECT id FROM customers WHERE phone = :phone"),
                    {"phone": phone},
                ).first()
                if existing_phone:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A customer with this phone number already exists.",
                    )

            conn.execute(
                text(
                    "INSERT INTO customers "
                    "(id, name, phone, email, address, doctor_name, allergies_or_notes) "
                    "VALUES (:id, :name, :phone, :email, :address, :doctor_name, :allergies_or_notes)"
                ),
                {
                    "id": customer_id,
                    "name": name,
                    "phone": phone,
                    "email": payload.get("email"),
                    "address": payload.get("address"),
                    "doctor_name": payload.get("doctor_name"),
                    "allergies_or_notes": payload.get("allergies_or_notes"),
                },
            )

            row = conn.execute(
                text(
                    "SELECT id, name, phone, email, address, doctor_name, "
                    "allergies_or_notes, created_at, updated_at "
                    "FROM customers WHERE id = :id"
                ),
                {"id": customer_id},
            ).mappings().first()
            return dict(row)
    except HTTPException:
        raise
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating customer.",
        ) from exc


def customer_update(engine: Engine, customer_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Partially updates a customer profile."""
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id, phone FROM customers WHERE id = :id"),
                {"id": customer_id},
            ).mappings().first()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found.",
                )

            updates: Dict[str, Any] = {}
            for field in ["name", "email", "address", "doctor_name", "allergies_or_notes"]:
                if field in payload and payload[field] is not None:
                    updates[field] = str(payload[field]).strip()

            if "phone" in payload:
                phone_raw = str(payload["phone"] or "").strip()
                updates["phone"] = phone_raw if phone_raw else None

            if "name" in updates and not updates["name"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Customer name cannot be empty.",
                )

            if "phone" in updates and updates["phone"]:
                dup = conn.execute(
                    text("SELECT id FROM customers WHERE phone = :phone AND id <> :id"),
                    {"phone": updates["phone"], "id": customer_id},
                ).first()
                if dup:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A customer with this phone number already exists.",
                    )

            if updates:
                set_clause = ", ".join(f"{col} = :{col}" for col in updates)
                conn.execute(
                    text(f"UPDATE customers SET {set_clause} WHERE id = :id"),
                    {**updates, "id": customer_id},
                )

            row = conn.execute(
                text(
                    "SELECT id, name, phone, email, address, doctor_name, "
                    "allergies_or_notes, created_at, updated_at "
                    "FROM customers WHERE id = :id"
                ),
                {"id": customer_id},
            ).mappings().first()
            return dict(row)
    except HTTPException:
        raise
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer with this phone number already exists.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating customer.",
        ) from exc


def customer_delete(engine: Engine, customer_id: str) -> Dict[str, Any]:
    """Deletes a customer profile."""
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM customers WHERE id = :id"),
                {"id": customer_id},
            ).first()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Customer not found.",
                )

            conn.execute(
                text("DELETE FROM customers WHERE id = :id"),
                {"id": customer_id},
            )
            return {"id": customer_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting customer.",
        ) from exc


# ---------------------------------------------------------------------------
# Invoices / Counter Sales (POS) Service
# ---------------------------------------------------------------------------

def invoice_list(
    engine: Engine,
    search: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Returns a paginated list of sales invoices with customer and cashier details.
    """
    safe_page = max(1, page)
    safe_limit = max(1, min(100, limit))
    offset = (safe_page - 1) * safe_limit

    conditions = []
    params: Dict[str, Any] = {"limit": safe_limit, "offset": offset}

    if search.strip():
        conditions.append(
            "(i.invoice_no LIKE :search OR c.name LIKE :search OR c.phone LIKE :search)"
        )
        params["search"] = f"%{search.strip()}%"

    if start_date:
        conditions.append("DATE(i.created_at) >= :start_date")
        params["start_date"] = start_date

    if end_date:
        conditions.append("DATE(i.created_at) <= :end_date")
        params["end_date"] = end_date

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        with engine.begin() as conn:
            total_count = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM invoices i "
                    f"LEFT JOIN customers c ON i.customer_id = c.id "
                    f"{where_clause}"
                ),
                params,
            ).scalar() or 0

            rows = conn.execute(
                text(
                    f"SELECT i.id, i.invoice_no, i.customer_id, c.name AS customer_name, "
                    f"c.phone AS customer_phone, i.total_amount, i.tax_amount, i.discount_amount, "
                    f"i.net_amount, i.payment_method, i.payment_status, i.doctor_prescription_ref, "
                    f"i.notes, i.created_by, p.full_name AS cashier_name, i.created_at "
                    f"FROM invoices i "
                    f"LEFT JOIN customers c ON i.customer_id = c.id "
                    f"LEFT JOIN profiles p ON i.created_by = p.id "
                    f"{where_clause} "
                    f"ORDER BY i.created_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().all()

            invoices = [dict(row) for row in rows]
            total_pages = max(1, (total_count + safe_limit - 1) // safe_limit) if total_count > 0 else 1

            return {
                "invoices": invoices,
                "total": total_count,
                "page": safe_page,
                "limit": safe_limit,
                "total_pages": total_pages,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing invoices.",
        ) from exc


def invoice_get(engine: Engine, invoice_id: str) -> Dict[str, Any]:
    """Retrieves an invoice with its line items."""
    try:
        with engine.begin() as conn:
            invoice = conn.execute(
                text(
                    "SELECT i.id, i.invoice_no, i.customer_id, c.name AS customer_name, "
                    "c.phone AS customer_phone, c.address AS customer_address, "
                    "i.total_amount, i.tax_amount, i.discount_amount, i.net_amount, "
                    "i.payment_method, i.payment_status, i.doctor_prescription_ref, "
                    "i.notes, i.created_by, p.full_name AS cashier_name, i.created_at "
                    "FROM invoices i "
                    "LEFT JOIN customers c ON i.customer_id = c.id "
                    "LEFT JOIN profiles p ON i.created_by = p.id "
                    "WHERE i.id = :id"
                ),
                {"id": invoice_id},
            ).mappings().first()
            if not invoice:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Invoice not found.",
                )

            items = conn.execute(
                text(
                    "SELECT it.id, it.medicine_id, m.name AS medicine_name, m.dosage_form, "
                    "it.batch_id, b.batch_no, b.expiry_date, it.quantity, it.unit_price, "
                    "it.purchase_cost_at_sale, it.tax_rate, it.discount_amount, it.subtotal "
                    "FROM invoice_items it "
                    "JOIN medicines m ON it.medicine_id = m.id "
                    "JOIN batches b ON it.batch_id = b.id "
                    "WHERE it.invoice_id = :invoice_id"
                ),
                {"invoice_id": invoice_id},
            ).mappings().all()

            result = dict(invoice)
            result["items"] = [dict(item) for item in items]
            return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching invoice.",
        ) from exc


def invoice_create(engine: Engine, payload: Dict[str, Any], created_by: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new counter sale invoice atomically:
    1. Validates line items and locks batch stock with FOR UPDATE.
    2. Enforces current_quantity >= quantity requested.
    3. Calculates subtotals, tax, discounts, and net_amount.
    4. Deducts batch stock and inserts immutable stock_movements ledger entry.
    5. Inserts invoice header and invoice items.
    """
    items_data = payload.get("items") or []
    if not items_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one item is required to create an invoice.",
        )

    customer_id = payload.get("customer_id")
    payment_method = str(payload.get("payment_method") or "cash").lower()
    if payment_method not in ("cash", "upi", "card", "credit", "split"):
        payment_method = "cash"
    payment_status = str(payload.get("payment_status") or "paid").lower()
    if payment_status not in ("paid", "pending", "partial", "cancelled"):
        payment_status = "paid"

    notes = payload.get("notes")
    doctor_prescription_ref = payload.get("doctor_prescription_ref")
    discount_override = Decimal(str(payload.get("discount_amount") or 0))

    invoice_id = str(uuid.uuid4())
    # Generate human-readable unique invoice number
    date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_suffix = uuid.uuid4().hex[:6].upper()
    invoice_no = f"INV-{date_prefix}-{short_suffix}"

    try:
        with engine.begin() as conn:
            # Check customer if supplied
            if customer_id:
                cust = conn.execute(
                    text("SELECT id FROM customers WHERE id = :id"),
                    {"id": customer_id},
                ).first()
                if not cust:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Referenced customer does not exist.",
                    )

            running_total = Decimal("0.00")
            running_tax = Decimal("0.00")
            running_discount = Decimal("0.00")
            prepared_items = []

            for item in items_data:
                med_id = item.get("medicine_id")
                b_id = item.get("batch_id")
                qty = int(item.get("quantity") or 0)
                if qty <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Invalid quantity {qty} for item. Must be greater than 0.",
                    )

                # Lock batch row for concurrency safety
                batch_row = conn.execute(
                    text(
                        "SELECT b.id, b.medicine_id, b.current_quantity, b.selling_price, "
                        "b.mrp, b.purchase_cost, m.name AS medicine_name "
                        "FROM batches b "
                        "JOIN medicines m ON b.medicine_id = m.id "
                        "WHERE b.id = :b_id AND b.medicine_id = :med_id "
                        "FOR UPDATE"
                    ),
                    {"b_id": b_id, "med_id": med_id},
                ).mappings().first()

                if not batch_row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Batch {b_id} for medicine {med_id} not found.",
                    )

                available_qty = int(batch_row["current_quantity"])
                if available_qty < qty:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Insufficient stock for '{batch_row['medicine_name']}'. "
                            f"Requested {qty}, available in batch is {available_qty}."
                        ),
                    )

                unit_price = Decimal(str(item.get("unit_price") or batch_row["selling_price"]))
                item_discount = Decimal(str(item.get("discount_amount") or 0))
                tax_rate = Decimal(str(item.get("tax_rate") or 0))
                cost_at_sale = Decimal(str(batch_row["purchase_cost"]))

                line_subtotal = (Decimal(qty) * unit_price) - item_discount
                if line_subtotal < Decimal("0.00"):
                    line_subtotal = Decimal("0.00")

                running_total += Decimal(qty) * unit_price
                running_discount += item_discount
                item_tax = (line_subtotal * tax_rate) / Decimal("100.00")
                running_tax += item_tax

                prepared_items.append({
                    "batch_id": b_id,
                    "medicine_id": med_id,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "purchase_cost_at_sale": cost_at_sale,
                    "tax_rate": tax_rate,
                    "discount_amount": item_discount,
                    "subtotal": line_subtotal,
                    "available_qty": available_qty,
                })

            if discount_override > running_discount:
                running_discount = discount_override

            net_amount = running_total + running_tax - running_discount
            if net_amount < Decimal("0.00"):
                net_amount = Decimal("0.00")

            # Insert invoice
            conn.execute(
                text(
                    "INSERT INTO invoices "
                    "(id, invoice_no, customer_id, total_amount, tax_amount, discount_amount, "
                    " net_amount, payment_method, payment_status, doctor_prescription_ref, "
                    " notes, created_by) "
                    "VALUES (:id, :invoice_no, :customer_id, :total_amount, :tax_amount, :discount_amount, "
                    "        :net_amount, :payment_method, :payment_status, :doctor_prescription_ref, "
                    "        :notes, :created_by)"
                ),
                {
                    "id": invoice_id,
                    "invoice_no": invoice_no,
                    "customer_id": customer_id,
                    "total_amount": running_total,
                    "tax_amount": running_tax,
                    "discount_amount": running_discount,
                    "net_amount": net_amount,
                    "payment_method": payment_method,
                    "payment_status": payment_status,
                    "doctor_prescription_ref": doctor_prescription_ref,
                    "notes": notes,
                    "created_by": created_by,
                },
            )

            # Insert line items & update stock
            for item in prepared_items:
                item_id = str(uuid.uuid4())
                conn.execute(
                    text(
                        "INSERT INTO invoice_items "
                        "(id, invoice_id, medicine_id, batch_id, quantity, unit_price, "
                        " purchase_cost_at_sale, tax_rate, discount_amount, subtotal) "
                        "VALUES (:id, :invoice_id, :medicine_id, :batch_id, :quantity, :unit_price, "
                        "        :purchase_cost_at_sale, :tax_rate, :discount_amount, :subtotal)"
                    ),
                    {
                        "id": item_id,
                        "invoice_id": invoice_id,
                        "medicine_id": item["medicine_id"],
                        "batch_id": item["batch_id"],
                        "quantity": item["quantity"],
                        "unit_price": item["unit_price"],
                        "purchase_cost_at_sale": item["purchase_cost_at_sale"],
                        "tax_rate": item["tax_rate"],
                        "discount_amount": item["discount_amount"],
                        "subtotal": item["subtotal"],
                    },
                )

                # Deduct inventory
                qty_before = item["available_qty"]
                qty_after = qty_before - item["quantity"]
                conn.execute(
                    text("UPDATE batches SET current_quantity = :after WHERE id = :batch_id"),
                    {"after": qty_after, "batch_id": item["batch_id"]},
                )

                # Insert immutable stock movement
                # Note trigger check_stock_movement_math requires: quantity_after = quantity_before + quantity_change
                # Here: qty_after = qty_before + (-item["quantity"])
                movement_id = str(uuid.uuid4())
                conn.execute(
                    text(
                        "INSERT INTO stock_movements "
                        "(id, medicine_id, batch_id, movement_type, quantity_change, "
                        " quantity_before, quantity_after, reference_id, reference_type, "
                        " reason, created_by) "
                        "VALUES (:id, :medicine_id, :batch_id, 'sale_out', :qty_change, "
                        "        :qty_before, :qty_after, :ref_id, 'invoice', "
                        "        :reason, :created_by)"
                    ),
                    {
                        "id": movement_id,
                        "medicine_id": item["medicine_id"],
                        "batch_id": item["batch_id"],
                        "qty_change": -item["quantity"],
                        "qty_before": qty_before,
                        "qty_after": qty_after,
                        "ref_id": invoice_id,
                        "reason": f"Sale dispatch {invoice_no}",
                        "created_by": created_by,
                    },
                )

        return invoice_get(engine, invoice_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while processing the sale: {str(exc)}",
        ) from exc


# ---------------------------------------------------------------------------
# Purchases / Procurement (Inward Stock) Service
# ---------------------------------------------------------------------------

def purchase_list(
    engine: Engine,
    search: str = "",
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Returns a paginated list of purchases with supplier details."""
    safe_page = max(1, page)
    safe_limit = max(1, min(100, limit))
    offset = (safe_page - 1) * safe_limit

    conditions = []
    params: Dict[str, Any] = {"limit": safe_limit, "offset": offset}

    if search.strip():
        conditions.append("(p.invoice_no LIKE :search OR s.name LIKE :search)")
        params["search"] = f"%{search.strip()}%"

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        with engine.begin() as conn:
            total_count = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM purchases p "
                    f"LEFT JOIN suppliers s ON p.supplier_id = s.id "
                    f"{where_clause}"
                ),
                params,
            ).scalar() or 0

            rows = conn.execute(
                text(
                    f"SELECT p.id, p.invoice_no, p.supplier_id, s.name AS supplier_name, "
                    f"p.purchase_date, p.total_amount, p.tax_amount, p.discount_amount, "
                    f"p.net_amount, p.payment_status, p.notes, p.created_by, "
                    f"u.full_name AS received_by_name, p.created_at "
                    f"FROM purchases p "
                    f"LEFT JOIN suppliers s ON p.supplier_id = s.id "
                    f"LEFT JOIN profiles u ON p.created_by = u.id "
                    f"{where_clause} "
                    f"ORDER BY p.purchase_date DESC, p.created_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().all()

            purchases = [dict(row) for row in rows]
            total_pages = max(1, (total_count + safe_limit - 1) // safe_limit) if total_count > 0 else 1

            return {
                "purchases": purchases,
                "total": total_count,
                "page": safe_page,
                "limit": safe_limit,
                "total_pages": total_pages,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing purchases.",
        ) from exc


def purchase_get(engine: Engine, purchase_id: str) -> Dict[str, Any]:
    """Retrieves a single purchase order with line items."""
    try:
        with engine.begin() as conn:
            purchase = conn.execute(
                text(
                    "SELECT p.id, p.invoice_no, p.supplier_id, s.name AS supplier_name, "
                    "p.purchase_date, p.total_amount, p.tax_amount, p.discount_amount, "
                    "p.net_amount, p.payment_status, p.notes, p.created_by, "
                    "u.full_name AS received_by_name, p.created_at "
                    "FROM purchases p "
                    "LEFT JOIN suppliers s ON p.supplier_id = s.id "
                    "LEFT JOIN profiles u ON p.created_by = u.id "
                    "WHERE p.id = :id"
                ),
                {"id": purchase_id},
            ).mappings().first()
            if not purchase:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Purchase record not found.",
                )

            items = conn.execute(
                text(
                    "SELECT pi.id, pi.medicine_id, m.name AS medicine_name, m.dosage_form, "
                    "pi.batch_id, b.batch_no, b.expiry_date, pi.quantity, pi.unit_cost, "
                    "pi.tax_rate, pi.subtotal "
                    "FROM purchase_items pi "
                    "JOIN medicines m ON pi.medicine_id = m.id "
                    "JOIN batches b ON pi.batch_id = b.id "
                    "WHERE pi.purchase_id = :purchase_id"
                ),
                {"purchase_id": purchase_id},
            ).mappings().all()

            result = dict(purchase)
            result["items"] = [dict(item) for item in items]
            return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching purchase record.",
        ) from exc


def purchase_create(engine: Engine, payload: Dict[str, Any], created_by: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates an inward purchase bill and updates stock:
    1. Validates supplier existence.
    2. Inserts or updates batches.
    3. Records immutable stock_movements with movement_type = 'purchase_in'.
    4. Inserts purchase header and purchase_items.
    """
    supplier_id = payload.get("supplier_id")
    if not supplier_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Supplier ID is required.",
        )

    items_data = payload.get("items") or []
    if not items_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one line item is required for a purchase bill.",
        )

    invoice_no = str(payload.get("invoice_no") or "").strip()
    if not invoice_no:
        invoice_no = f"PUR-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    purchase_date = payload.get("purchase_date") or date.today().isoformat()
    payment_status = str(payload.get("payment_status") or "paid").lower()
    notes = payload.get("notes")

    purchase_id = str(uuid.uuid4())

    try:
        with engine.begin() as conn:
            supp = conn.execute(
                text("SELECT id FROM suppliers WHERE id = :id"),
                {"id": supplier_id},
            ).first()
            if not supp:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Referenced supplier does not exist.",
                )

            # Check duplicate supplier + invoice_no
            dup = conn.execute(
                text("SELECT id FROM purchases WHERE supplier_id = :supplier_id AND invoice_no = :invoice_no"),
                {"supplier_id": supplier_id, "invoice_no": invoice_no},
            ).first()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Invoice number '{invoice_no}' already exists for this supplier.",
                )

            running_total = Decimal("0.00")
            running_tax = Decimal("0.00")
            running_discount = Decimal(str(payload.get("discount_amount") or 0))
            prepared_items = []

            for item in items_data:
                med_id = item.get("medicine_id")
                batch_no = str(item.get("batch_no") or "").strip()
                qty = int(item.get("quantity") or 0)
                unit_cost = Decimal(str(item.get("unit_cost") or 0))
                mrp = Decimal(str(item.get("mrp") or unit_cost))
                selling_price = Decimal(str(item.get("selling_price") or mrp))
                expiry_date = item.get("expiry_date")
                mfg_date = item.get("mfg_date")
                tax_rate = Decimal(str(item.get("tax_rate") or 0))

                if not med_id or not batch_no or not expiry_date:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Medicine ID, batch number, and expiry date are required for each purchase item.",
                    )
                if qty <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Quantity must be greater than 0 for batch {batch_no}.",
                    )
                if unit_cost < Decimal("0") or mrp < Decimal("0") or selling_price < Decimal("0"):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Unit cost, MRP, and selling price cannot be negative for batch {batch_no}.",
                    )
                if selling_price > mrp:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Selling price ({selling_price}) cannot exceed MRP ({mrp}) for batch {batch_no}.",
                    )
                if mfg_date and expiry_date and str(mfg_date) >= str(expiry_date):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Item for batch {batch_no}: mfg_date must be earlier than expiry_date.",
                    )

                # Verify medicine exists
                med = conn.execute(
                    text("SELECT id FROM medicines WHERE id = :id"),
                    {"id": med_id},
                ).first()
                if not med:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Medicine ID '{med_id}' not found.",
                    )

                subtotal = Decimal(qty) * unit_cost
                item_tax = (subtotal * tax_rate) / Decimal("100.00")
                running_total += subtotal
                running_tax += item_tax

                # Check if batch exists
                existing_batch = conn.execute(
                    text(
                        "SELECT id, current_quantity FROM batches "
                        "WHERE medicine_id = :medicine_id AND batch_no = :batch_no "
                        "FOR UPDATE"
                    ),
                    {"medicine_id": med_id, "batch_no": batch_no},
                ).mappings().first()

                if existing_batch:
                    batch_id = existing_batch["id"]
                    qty_before = int(existing_batch["current_quantity"])
                    qty_after = qty_before + qty
                    conn.execute(
                        text(
                            "UPDATE batches SET current_quantity = :after, "
                            "purchase_cost = :cost, mrp = :mrp, selling_price = :selling_price "
                            "WHERE id = :id"
                        ),
                        {
                            "after": qty_after,
                            "cost": unit_cost,
                            "mrp": mrp,
                            "selling_price": selling_price,
                            "id": batch_id,
                        },
                    )
                else:
                    batch_id = str(uuid.uuid4())
                    qty_before = 0
                    qty_after = qty
                    conn.execute(
                        text(
                            "INSERT INTO batches "
                            "(id, medicine_id, supplier_id, batch_no, mfg_date, expiry_date, "
                            " purchase_cost, mrp, selling_price, initial_quantity, current_quantity) "
                            "VALUES (:id, :medicine_id, :supplier_id, :batch_no, :mfg_date, :expiry_date, "
                            "        :purchase_cost, :mrp, :selling_price, :initial_quantity, :current_quantity)"
                        ),
                        {
                            "id": batch_id,
                            "medicine_id": med_id,
                            "supplier_id": supplier_id,
                            "batch_no": batch_no,
                            "mfg_date": mfg_date,
                            "expiry_date": expiry_date,
                            "purchase_cost": unit_cost,
                            "mrp": mrp,
                            "selling_price": selling_price,
                            "initial_quantity": qty,
                            "current_quantity": qty,
                        },
                    )

                prepared_items.append({
                    "medicine_id": med_id,
                    "batch_id": batch_id,
                    "quantity": qty,
                    "unit_cost": unit_cost,
                    "tax_rate": tax_rate,
                    "subtotal": subtotal,
                    "qty_before": qty_before,
                    "qty_after": qty_after,
                })

            net_amount = running_total + running_tax - running_discount
            if net_amount < Decimal("0.00"):
                net_amount = Decimal("0.00")

            # Insert purchase header
            conn.execute(
                text(
                    "INSERT INTO purchases "
                    "(id, invoice_no, supplier_id, purchase_date, total_amount, "
                    " tax_amount, discount_amount, net_amount, payment_status, notes, created_by) "
                    "VALUES (:id, :invoice_no, :supplier_id, :purchase_date, :total_amount, "
                    "        :tax_amount, :discount_amount, :net_amount, :payment_status, :notes, :created_by)"
                ),
                {
                    "id": purchase_id,
                    "invoice_no": invoice_no,
                    "supplier_id": supplier_id,
                    "purchase_date": purchase_date,
                    "total_amount": running_total,
                    "tax_amount": running_tax,
                    "discount_amount": running_discount,
                    "net_amount": net_amount,
                    "payment_status": payment_status,
                    "notes": notes,
                    "created_by": created_by,
                },
            )

            # Insert purchase items and ledger movements
            for item in prepared_items:
                conn.execute(
                    text(
                        "INSERT INTO purchase_items "
                        "(id, purchase_id, medicine_id, batch_id, quantity, unit_cost, tax_rate, subtotal) "
                        "VALUES (:id, :purchase_id, :medicine_id, :batch_id, :quantity, :unit_cost, :tax_rate, :subtotal)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "purchase_id": purchase_id,
                        "medicine_id": item["medicine_id"],
                        "batch_id": item["batch_id"],
                        "quantity": item["quantity"],
                        "unit_cost": item["unit_cost"],
                        "tax_rate": item["tax_rate"],
                        "subtotal": item["subtotal"],
                    },
                )

                # Insert immutable stock movement (purchase_in)
                # math integrity: qty_after = qty_before + quantity_change
                conn.execute(
                    text(
                        "INSERT INTO stock_movements "
                        "(id, medicine_id, batch_id, movement_type, quantity_change, "
                        " quantity_before, quantity_after, reference_id, reference_type, "
                        " reason, created_by) "
                        "VALUES (:id, :medicine_id, :batch_id, 'purchase_in', :qty_change, "
                        "        :qty_before, :qty_after, :ref_id, 'purchase', "
                        "        :reason, :created_by)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "medicine_id": item["medicine_id"],
                        "batch_id": item["batch_id"],
                        "qty_change": item["quantity"],
                        "qty_before": item["qty_before"],
                        "qty_after": item["qty_after"],
                        "ref_id": purchase_id,
                        "reason": f"Procurement receipt {invoice_no}",
                        "created_by": created_by,
                    },
                )

        return purchase_get(engine, purchase_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while recording the purchase: {str(exc)}",
        ) from exc


# ---------------------------------------------------------------------------
# Expenses Service
# ---------------------------------------------------------------------------

def expense_list(
    engine: Engine,
    search: str = "",
    category: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """Returns a paginated list of operational store expenses."""
    safe_page = max(1, page)
    safe_limit = max(1, min(100, limit))
    offset = (safe_page - 1) * safe_limit

    conditions = []
    params: Dict[str, Any] = {"limit": safe_limit, "offset": offset}

    if search.strip():
        conditions.append("(e.title LIKE :search OR e.notes LIKE :search)")
        params["search"] = f"%{search.strip()}%"

    if category.strip():
        conditions.append("e.category = :category")
        params["category"] = category.strip()

    if start_date:
        conditions.append("e.expense_date >= :start_date")
        params["start_date"] = start_date

    if end_date:
        conditions.append("e.expense_date <= :end_date")
        params["end_date"] = end_date

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        with engine.begin() as conn:
            total_count = conn.execute(
                text(f"SELECT COUNT(*) FROM expenses e {where_clause}"),
                params,
            ).scalar() or 0

            rows = conn.execute(
                text(
                    f"SELECT e.id, e.title, e.category, e.amount, e.expense_date, "
                    f"e.payment_method, e.receipt_url, e.notes, e.created_by, "
                    f"p.full_name AS created_by_name, e.created_at "
                    f"FROM expenses e "
                    f"LEFT JOIN profiles p ON e.created_by = p.id "
                    f"{where_clause} "
                    f"ORDER BY e.expense_date DESC, e.created_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().all()

            expenses = [dict(row) for row in rows]
            total_pages = max(1, (total_count + safe_limit - 1) // safe_limit) if total_count > 0 else 1

            return {
                "expenses": expenses,
                "total": total_count,
                "page": safe_page,
                "limit": safe_limit,
                "total_pages": total_pages,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing expenses.",
        ) from exc


def expense_create(engine: Engine, payload: Dict[str, Any], created_by: Optional[str] = None) -> Dict[str, Any]:
    """Creates a new store operating expense."""
    title = str(payload.get("title") or "").strip()
    category = str(payload.get("category") or "").strip()
    amount = Decimal(str(payload.get("amount") or 0))

    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expense title is required.",
        )
    if not category:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expense category is required.",
        )
    if amount <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expense amount must be greater than zero.",
        )

    expense_date = payload.get("expense_date") or date.today().isoformat()
    payment_method = str(payload.get("payment_method") or "cash")
    receipt_url = payload.get("receipt_url")
    notes = payload.get("notes")

    expense_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO expenses "
                    "(id, title, category, amount, expense_date, payment_method, receipt_url, notes, created_by) "
                    "VALUES (:id, :title, :category, :amount, :expense_date, :payment_method, :receipt_url, :notes, :created_by)"
                ),
                {
                    "id": expense_id,
                    "title": title,
                    "category": category,
                    "amount": amount,
                    "expense_date": expense_date,
                    "payment_method": payment_method,
                    "receipt_url": receipt_url,
                    "notes": notes,
                    "created_by": created_by,
                },
            )

            row = conn.execute(
                text(
                    "SELECT e.id, e.title, e.category, e.amount, e.expense_date, "
                    "e.payment_method, e.receipt_url, e.notes, e.created_by, "
                    "p.full_name AS created_by_name, e.created_at "
                    "FROM expenses e "
                    "LEFT JOIN profiles p ON e.created_by = p.id "
                    "WHERE e.id = :id"
                ),
                {"id": expense_id},
            ).mappings().first()
            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while recording the expense.",
        ) from exc


def expense_delete(engine: Engine, expense_id: str) -> Dict[str, Any]:
    """Deletes an expense record."""
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM expenses WHERE id = :id"),
                {"id": expense_id},
            ).first()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Expense record not found.",
                )

            conn.execute(
                text("DELETE FROM expenses WHERE id = :id"),
                {"id": expense_id},
            )
            return {"id": expense_id, "deleted": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting expense.",
        ) from exc


# ---------------------------------------------------------------------------
# Dashboard Analytics & Reports Service
# ---------------------------------------------------------------------------

def dashboard_stats(engine: Engine) -> Dict[str, Any]:
    """
    Returns aggregated metrics for the MediShop executive dashboard:
    - Today's sales total and transaction count
    - Active medicines catalog count
    - Low-stock medicine count
    - Batches expiring within 90 days
    - Category distribution
    - Recent sales transactions
    - 7-day revenue trend
    """
    try:
        with engine.begin() as conn:
            # Today's sales
            today_sales_row = conn.execute(
                text(
                    "SELECT COALESCE(SUM(net_amount), 0) AS total_revenue, "
                    "COUNT(*) AS tx_count "
                    "FROM invoices "
                    "WHERE DATE(created_at) = CURRENT_DATE() AND payment_status != 'cancelled'"
                )
            ).mappings().first()
            today_revenue = float(today_sales_row["total_revenue"] or 0)
            today_count = int(today_sales_row["tx_count"] or 0)

            # Total active medicines
            total_meds = conn.execute(
                text("SELECT COUNT(*) FROM medicines WHERE is_active = TRUE")
            ).scalar() or 0

            # Low stock medicines (sum of batch quantities < min_stock_alert)
            low_stock_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM ("
                    "  SELECT m.id, m.min_stock_alert, COALESCE(SUM(b.current_quantity), 0) AS total_stock "
                    "  FROM medicines m "
                    "  LEFT JOIN batches b ON m.id = b.medicine_id "
                    "  WHERE m.is_active = TRUE "
                    "  GROUP BY m.id, m.min_stock_alert "
                    "  HAVING total_stock < m.min_stock_alert"
                    ") AS low_stock_items"
                )
            ).scalar() or 0

            # Expiring batches in next 90 days
            expiring_batches = conn.execute(
                text(
                    "SELECT COUNT(*) FROM batches "
                    "WHERE expiry_date <= DATE_ADD(CURRENT_DATE(), INTERVAL 90 DAY) "
                    "AND current_quantity > 0"
                )
            ).scalar() or 0

            # Category distribution (top 6)
            cat_rows = conn.execute(
                text(
                    "SELECT c.name, COUNT(m.id) AS medicine_count "
                    "FROM categories c "
                    "LEFT JOIN medicines m ON c.id = m.category_id AND m.is_active = TRUE "
                    "GROUP BY c.id, c.name "
                    "ORDER BY medicine_count DESC "
                    "LIMIT 6"
                )
            ).mappings().all()
            category_distribution = [
                {"name": row["name"], "count": int(row["medicine_count"])}
                for row in cat_rows
            ]

            # Recent sales (last 6)
            recent_sales_rows = conn.execute(
                text(
                    "SELECT i.id, i.invoice_no, COALESCE(c.name, 'Walk-in Customer') AS customer_name, "
                    "i.net_amount, i.payment_method, i.payment_status, i.created_at "
                    "FROM invoices i "
                    "LEFT JOIN customers c ON i.customer_id = c.id "
                    "ORDER BY i.created_at DESC "
                    "LIMIT 6"
                )
            ).mappings().all()
            recent_sales = [
                {
                    "id": r["id"],
                    "invoice_no": r["invoice_no"],
                    "customer_name": r["customer_name"],
                    "amount": float(r["net_amount"]),
                    "payment_method": r["payment_method"],
                    "status": r["payment_status"],
                    "created_at": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else str(r["created_at"]),
                }
                for r in recent_sales_rows
            ]

            # 7-day revenue trend
            trend_rows = conn.execute(
                text(
                    "SELECT DATE(created_at) AS sale_date, "
                    "COALESCE(SUM(net_amount), 0) AS daily_revenue, "
                    "COUNT(*) AS daily_orders "
                    "FROM invoices "
                    "WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 DAY) "
                    "AND payment_status != 'cancelled' "
                    "GROUP BY DATE(created_at) "
                    "ORDER BY sale_date ASC"
                )
            ).mappings().all()
            sales_trend = [
                {
                    "date": str(row["sale_date"]),
                    "revenue": float(row["daily_revenue"]),
                    "orders": int(row["daily_orders"]),
                }
                for row in trend_rows
            ]

            return {
                "today_revenue": today_revenue,
                "today_orders": today_count,
                "total_medicines": total_meds,
                "low_stock_count": low_stock_count,
                "expiring_batches_count": expiring_batches,
                "category_distribution": category_distribution,
                "recent_sales": recent_sales,
                "sales_trend": sales_trend,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating dashboard metrics.",
        ) from exc


def reports_summary(
    engine: Engine,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns financial P&L and operational reporting summary:
    - Gross sales revenue
    - Cost of goods sold (COGS)
    - Gross profit & margin
    - Operational expenses
    - Net profit
    - Top selling products
    """
    date_cond_inv = []
    params: Dict[str, Any] = {}
    if start_date:
        date_cond_inv.append("DATE(i.created_at) >= :start_date")
        params["start_date"] = start_date
    if end_date:
        date_cond_inv.append("DATE(i.created_at) <= :end_date")
        params["end_date"] = end_date

    where_inv = f"AND {' AND '.join(date_cond_inv)}" if date_cond_inv else ""

    date_cond_exp = []
    if start_date:
        date_cond_exp.append("expense_date >= :start_date")
    if end_date:
        date_cond_exp.append("expense_date <= :end_date")
    where_exp = f"WHERE {' AND '.join(date_cond_exp)}" if date_cond_exp else ""

    try:
        with engine.begin() as conn:
            # Sales & COGS
            pnl_row = conn.execute(
                text(
                    f"SELECT "
                    f"  COALESCE(SUM(it.subtotal), 0) AS total_revenue, "
                    f"  COALESCE(SUM(it.purchase_cost_at_sale * it.quantity), 0) AS total_cogs, "
                    f"  COUNT(DISTINCT i.id) AS total_invoices "
                    f"FROM invoices i "
                    f"JOIN invoice_items it ON i.id = it.invoice_id "
                    f"WHERE i.payment_status != 'cancelled' {where_inv}"
                ),
                params,
            ).mappings().first()

            revenue = float(pnl_row["total_revenue"] or 0)
            cogs = float(pnl_row["total_cogs"] or 0)
            gross_profit = revenue - cogs
            gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0.0

            # Total expenses
            total_expenses = conn.execute(
                text(f"SELECT COALESCE(SUM(amount), 0) FROM expenses {where_exp}"),
                params,
            ).scalar() or 0
            total_expenses = float(total_expenses)
            net_profit = gross_profit - total_expenses

            # Top 10 medicines sold
            top_medicines_rows = conn.execute(
                text(
                    f"SELECT m.id, m.name, m.dosage_form, "
                    f"  SUM(it.quantity) AS total_quantity, "
                    f"  SUM(it.subtotal) AS total_revenue "
                    f"FROM invoice_items it "
                    f"JOIN medicines m ON it.medicine_id = m.id "
                    f"JOIN invoices i ON it.invoice_id = i.id "
                    f"WHERE i.payment_status != 'cancelled' {where_inv} "
                    f"GROUP BY m.id, m.name, m.dosage_form "
                    f"ORDER BY total_quantity DESC "
                    f"LIMIT 10"
                ),
                params,
            ).mappings().all()

            top_medicines = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "dosage_form": r["dosage_form"],
                    "quantity_sold": int(r["total_quantity"]),
                    "revenue": float(r["total_revenue"]),
                }
                for r in top_medicines_rows
            ]

            return {
                "total_revenue": revenue,
                "total_cogs": cogs,
                "gross_profit": gross_profit,
                "gross_margin_percent": round(gross_margin, 2),
                "total_expenses": total_expenses,
                "net_profit": net_profit,
                "total_invoices": int(pnl_row["total_invoices"] or 0),
                "top_medicines": top_medicines,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating reports summary.",
        ) from exc

