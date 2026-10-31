"""
MediShop Medicine & Inventory Service
=====================================
Business-logic layer for medicine catalogue and inventory read/write operations
against the MySQL database (medicines, categories, brands, batches, suppliers).

All database access uses parameterized SQLAlchemy ``text()`` queries — never
string-formatted SQL. Errors are converted to generic FastAPI ``HTTPException``
responses without leaking internal database details.
"""

import math
import re
import uuid
from typing import Any, Dict, Optional

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status


DOSAGE_FORMS = (
    "Tablet",
    "Capsule",
    "Syrup",
    "Injection",
    "Ointment",
    "Drops",
    "Inhaler",
    "Other",
)


def _invalid_dosage_form(dosage_form: Optional[str]) -> bool:
    return dosage_form is None or dosage_form not in DOSAGE_FORMS


# ---------------------------------------------------------------------------
# Medicine catalogue
# ---------------------------------------------------------------------------

def medicine_list(
    engine: Engine,
    search: str = "",
    category_id: str = "",
    brand_id: str = "",
    is_active: Optional[bool] = True,
    page: int = 1,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Returns a paginated, searchable list of medicines.

    Query filters:
    - ``search``: matches medicine name or generic name (case-insensitive).
    - ``category_id`` / ``brand_id``: optional exact filters.
    - ``is_active``: defaults to True (active catalogue entries only), or None for all.

    Response: ``{ medicines: [...], total, page, limit, total_pages }``.
    """
    try:
        with engine.begin() as conn:
            conditions = []
            params: Dict[str, Any] = {}
            if is_active is not None:
                conditions.append("m.is_active = :is_active")
                params["is_active"] = bool(is_active)

            if search and search.strip():
                conditions.append("(LOWER(m.name) LIKE LOWER(:q) OR LOWER(m.generic_name) LIKE LOWER(:q))")
                params["q"] = f"%{search.strip().lower()}%"

            if category_id:
                conditions.append("m.category_id = :category_id")
                params["category_id"] = category_id

            if brand_id:
                conditions.append("m.brand_id = :brand_id")
                params["brand_id"] = brand_id

            where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

            total = conn.execute(
                text(f"SELECT COUNT(*) AS total FROM medicines m{where_clause}"),
                params,
            ).scalar_one()

            page = max(1, page)
            limit = max(1, min(limit, 100))
            offset = (page - 1) * limit

            rows = conn.execute(
                text(
                    "SELECT m.id, m.name, m.generic_name, m.dosage_form, m.strength, m.unit, "
                    "m.hsn_code, m.requires_prescription, m.min_stock_alert, m.is_active, "
                    "m.created_at, m.updated_at, "
                    "COALESCE((SELECT SUM(b.current_quantity) FROM batches b WHERE b.medicine_id = m.id), 0) AS current_stock, "
                    "c.id AS category_id, c.name AS category_name, "
                    "b.id AS brand_id, b.name AS brand_name "
                    "FROM medicines m "
                    "LEFT JOIN categories c ON m.category_id = c.id "
                    "LEFT JOIN brands b ON m.brand_id = b.id "
                    f"{where_clause} "
                    "ORDER BY m.name ASC "
                    "LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": limit, "offset": offset},
            ).mappings().all()

            medicines = [dict(row) for row in rows]

            return {
                "medicines": medicines,
                "total": int(total),
                "page": page,
                "limit": limit,
                "total_pages": max(1, math.ceil(int(total) / limit)) if int(total) > 0 else 0,
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the medicine catalogue.",
        ) from exc


def medicine_get(engine: Engine, medicine_id: str) -> Dict[str, Any]:
    """Returns a single medicine by ID. Raises HTTP 404 when not found."""
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT m.id, m.name, m.generic_name, m.dosage_form, m.strength, m.unit, "
                    "m.hsn_code, m.requires_prescription, m.min_stock_alert, m.is_active, "
                    "m.created_at, m.updated_at, "
                    "c.id AS category_id, c.name AS category_name, "
                    "b.id AS brand_id, b.name AS brand_name "
                    "FROM medicines m "
                    "LEFT JOIN categories c ON m.category_id = c.id "
                    "LEFT JOIN brands b ON m.brand_id = b.id "
                    "WHERE m.id = :medicine_id"
                ),
                {"medicine_id": medicine_id},
            ).mappings().first()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Medicine not found.",
                )

            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the medicine.",
        ) from exc


def medicine_create(engine: Engine, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new medicine. Raises HTTP 422 when the category does not exist.
    """
    category_id = payload.get("category_id")
    if not category_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid category is required.",
        )

    dosage_form = payload.get("dosage_form")
    if _invalid_dosage_form(dosage_form):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid dosage_form '{dosage_form}'. "
                f"Must be one of: {', '.join(DOSAGE_FORMS)}."
            ),
        )

    try:
        with engine.begin() as conn:
            category = conn.execute(
                text("SELECT id FROM categories WHERE id = :id"),
                {"id": category_id},
            ).first()
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid category: the referenced category does not exist.",
                )

            medicine_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO medicines "
                    "(id, name, generic_name, category_id, brand_id, dosage_form, strength, unit, "
                    " hsn_code, requires_prescription, min_stock_alert, is_active) "
                    "VALUES (:id, :name, :generic_name, :category_id, :brand_id, :dosage_form, :strength, "
                    "        :unit, :hsn_code, :requires_prescription, :min_stock_alert, :is_active)"
                ),
                {
                    "id": medicine_id,
                    "name": payload.get("name"),
                    "generic_name": payload.get("generic_name"),
                    "category_id": category_id,
                    "brand_id": payload.get("brand_id"),
                    "dosage_form": payload.get("dosage_form"),
                    "strength": payload.get("strength"),
                    "unit": payload.get("unit") or "Strip",
                    "hsn_code": payload.get("hsn_code"),
                    "requires_prescription": bool(payload.get("requires_prescription") or False),
                    "min_stock_alert": int(payload.get("min_stock_alert") or 0),
                    "is_active": bool(payload.get("is_active") if "is_active" in payload else True),
                },
            )

            row = conn.execute(
                text(
                    "SELECT m.id, m.name, m.generic_name, m.dosage_form, m.strength, m.unit, "
                    "m.hsn_code, m.requires_prescription, m.min_stock_alert, m.is_active, "
                    "m.created_at, m.updated_at, "
                    "c.id AS category_id, c.name AS category_name, "
                    "b.id AS brand_id, b.name AS brand_name "
                    "FROM medicines m "
                    "LEFT JOIN categories c ON m.category_id = c.id "
                    "LEFT JOIN brands b ON m.brand_id = b.id "
                    "WHERE m.id = :medicine_id"
                ),
                {"medicine_id": medicine_id},
            ).mappings().first()

            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the medicine.",
        ) from exc


def medicine_update(engine: Engine, medicine_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Partially updates a medicine. Supports deactivation via ``is_active: False``.
    Raises HTTP 404 when the medicine does not exist.
    """
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM medicines WHERE id = :medicine_id"),
                {"medicine_id": medicine_id},
            ).first()
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Medicine not found.",
                )

            if payload.get("dosage_form") is not None and _invalid_dosage_form(payload.get("dosage_form")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid dosage_form '{payload.get('dosage_form')}'. "
                        f"Must be one of: {', '.join(DOSAGE_FORMS)}."
                    ),
                )

            updates = {}
            if "name" in payload and payload.get("name") is not None:
                updates["name"] = payload["name"]
            if "generic_name" in payload and payload.get("generic_name") is not None:
                updates["generic_name"] = payload["generic_name"]
            if "category_id" in payload and payload.get("category_id"):
                updates["category_id"] = payload["category_id"]
            if "brand_id" in payload and payload.get("brand_id"):
                updates["brand_id"] = payload["brand_id"]
            if "dosage_form" in payload and payload.get("dosage_form"):
                updates["dosage_form"] = payload["dosage_form"]
            if "strength" in payload and payload.get("strength") is not None:
                updates["strength"] = payload["strength"]
            if "unit" in payload and payload.get("unit"):
                updates["unit"] = payload["unit"]
            if "hsn_code" in payload and payload.get("hsn_code") is not None:
                updates["hsn_code"] = payload["hsn_code"]
            if "requires_prescription" in payload and payload.get("requires_prescription") is not None:
                updates["requires_prescription"] = bool(payload["requires_prescription"])
            if "min_stock_alert" in payload and payload.get("min_stock_alert") is not None:
                updates["min_stock_alert"] = int(payload["min_stock_alert"])
            if "is_active" in payload and payload.get("is_active") is not None:
                updates["is_active"] = bool(payload["is_active"])

            if updates:
                set_clause = ", ".join(f"{key} = :val_{i}" for i, key in enumerate(updates))
                params = {f"val_{i}": value for i, value in enumerate(updates.values())}
                params["medicine_id"] = medicine_id
                conn.execute(
                    text(f"UPDATE medicines SET {set_clause}, updated_at = NOW() WHERE id = :medicine_id"),
                    params,
                )

            row = conn.execute(
                text(
                    "SELECT m.id, m.name, m.generic_name, m.dosage_form, m.strength, m.unit, "
                    "m.hsn_code, m.requires_prescription, m.min_stock_alert, m.is_active, "
                    "m.created_at, m.updated_at, "
                    "c.id AS category_id, c.name AS category_name, "
                    "b.id AS brand_id, b.name AS brand_name "
                    "FROM medicines m "
                    "LEFT JOIN categories c ON m.category_id = c.id "
                    "LEFT JOIN brands b ON m.brand_id = b.id "
                    "WHERE m.id = :medicine_id"
                ),
                {"medicine_id": medicine_id},
            ).mappings().first()

            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found.")

            return dict(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the medicine.",
        ) from exc


# ---------------------------------------------------------------------------
# Inventory & stock
# ---------------------------------------------------------------------------

def medicine_inventory(engine: Engine, medicine_id: str) -> Dict[str, Any]:
    """
    Returns inventory/stock information for a medicine: aggregate current
    stock, low-stock flag, and all batch quantities with expiry dates.

    Raises HTTP 404 when the medicine does not exist.
    """
    try:
        with engine.begin() as conn:
            medicine = conn.execute(
                text(
                    "SELECT m.id, m.name, m.min_stock_alert, m.is_active "
                    "FROM medicines m WHERE m.id = :medicine_id"
                ),
                {"medicine_id": medicine_id},
            ).mappings().first()
            if not medicine:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found.")

            stock_row = conn.execute(
                text(
                    "SELECT COALESCE(SUM(b.current_quantity), 0) AS current_stock "
                    "FROM batches b WHERE b.medicine_id = :medicine_id"
                ),
                {"medicine_id": medicine_id},
            ).first()
            current_stock = int(stock_row[0] or 0) if stock_row is not None else 0

            batches = [
                dict(batch)
                for batch in conn.execute(
                    text(
                        "SELECT b.id, b.batch_no, b.mfg_date, b.expiry_date, b.purchase_cost, "
                        "b.mrp, b.selling_price, b.initial_quantity, b.current_quantity, "
                        "s.id AS supplier_id, s.name AS supplier_name "
                        "FROM batches b "
                        "LEFT JOIN suppliers s ON b.supplier_id = s.id "
                        "WHERE b.medicine_id = :medicine_id "
                        "ORDER BY b.expiry_date ASC, b.batch_no ASC"
                    ),
                    {"medicine_id": medicine_id},
                ).mappings().all()
            ]

            return {
                "medicine_id": medicine["id"],
                "medicine_name": medicine["name"],
                "min_stock_alert": int(medicine["min_stock_alert"] or 0),
                "is_active": bool(medicine["is_active"]),
                "current_stock": current_stock,
                "is_low_stock": current_stock < int(medicine["min_stock_alert"] or 0),
                "batches": batches,
            }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the inventory.",
        ) from exc


# ---------------------------------------------------------------------------
# Lookup collections
# ---------------------------------------------------------------------------

def medicine_batch_create(engine: Engine, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new medicine batch (stock intake).

    - Validates the referenced medicine exists (404 when missing).
    - Validates the optional supplier exists (422 when missing).
    - Validates ``mfg_date < expiry_date`` (422 otherwise).
    - Validates ``selling_price <= mrp`` (422 otherwise).
    - Rejects duplicate ``(medicine_id, batch_no)`` with HTTP 409.
    - Sets ``initial_quantity`` and ``current_quantity`` to the received quantity.

    Raises HTTP 422 for invalid payloads, HTTP 404 for unknown medicine/supplier,
    HTTP 409 for duplicate batches, and HTTP 500 for unexpected database errors.
    """
    medicine_id = payload.get("medicine_id")
    batch_no = payload.get("batch_no")
    expiry_date = payload.get("expiry_date")
    purchase_cost = Decimal(str(payload.get("purchase_cost") or 0))
    mrp = Decimal(str(payload.get("mrp") or 0))
    selling_price = Decimal(str(payload.get("selling_price") or 0))
    initial_quantity = int(payload.get("initial_quantity") or 0)
    mfg_date = payload.get("mfg_date")
    supplier_id = payload.get("supplier_id")

    if mfg_date is not None and expiry_date is not None and mfg_date >= expiry_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid batch: mfg_date must be earlier than expiry_date.",
        )

    if selling_price > mrp:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid batch: selling_price must not exceed mrp.",
        )

    try:
        with engine.begin() as conn:
            medicine = conn.execute(
                text("SELECT id FROM medicines WHERE id = :medicine_id"),
                {"medicine_id": medicine_id},
            ).first()
            if not medicine:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Medicine not found.",
                )

            if supplier_id:
                supplier = conn.execute(
                    text("SELECT id FROM suppliers WHERE id = :id"),
                    {"id": supplier_id},
                ).first()
                if not supplier:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Invalid supplier: the referenced supplier does not exist.",
                    )

            duplicate = conn.execute(
                text(
                    "SELECT id FROM batches "
                    "WHERE medicine_id = :medicine_id AND batch_no = :batch_no"
                ),
                {"medicine_id": medicine_id, "batch_no": batch_no},
            ).first()
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Batch already exists for this medicine with the same batch number.",
                )

            batch_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO batches "
                    "(id, medicine_id, supplier_id, batch_no, mfg_date, expiry_date, "
                    " purchase_cost, mrp, selling_price, initial_quantity, current_quantity) "
                    "VALUES (:id, :medicine_id, :supplier_id, :batch_no, :mfg_date, :expiry_date, "
                    "        :purchase_cost, :mrp, :selling_price, :initial_quantity, :initial_quantity)"
                ),
                {
                    "id": batch_id,
                    "medicine_id": medicine_id,
                    "supplier_id": supplier_id,
                    "batch_no": batch_no,
                    "mfg_date": mfg_date,
                    "expiry_date": expiry_date,
                    "purchase_cost": purchase_cost,
                    "mrp": mrp,
                    "selling_price": selling_price,
                    "initial_quantity": initial_quantity,
                },
            )

            batch = conn.execute(
                text(
                    "SELECT b.id, b.medicine_id, b.batch_no, b.mfg_date, b.expiry_date, "
                    "b.purchase_cost, b.mrp, b.selling_price, b.initial_quantity, "
                    "b.current_quantity, s.id AS supplier_id, s.name AS supplier_name "
                    "FROM batches b "
                    "LEFT JOIN suppliers s ON b.supplier_id = s.id "
                    "WHERE b.id = :batch_id"
                ),
                {"batch_id": batch_id},
            ).mappings().first()

            return dict(batch)
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1062:  # MySQL ER_DUP_ENTRY -> genuine duplicate batch
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Batch already exists for this medicine with the same batch number.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the batch.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the batch.",
        ) from exc


def medicine_categories(engine: Engine) -> list:
    """Returns all medicine categories for dropdowns / filters."""
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, name, slug, description, storage_temperature "
                    "FROM categories ORDER BY name ASC"
                )
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching categories.",
        ) from exc


def medicine_inventory_list(
    engine: Engine,
    search: str = "",
    page: int = 1,
    limit: int = 20,
    is_active: bool = True,
) -> Dict[str, Any]:
    """
    Returns a paginated inventory list (medicine + aggregate stock + batches).

    Used by the medicine dashboard to derive low-stock counts and the expiry
    watchlist. Batches are attached per medicine via :func:`medicine_inventory`.
    """
    listing = medicine_list(
        engine,
        search=search,
        category_id="",
        brand_id="",
        is_active=is_active,
        page=page,
        limit=limit,
    )
    entries = [medicine_inventory(engine, medicine["id"]) for medicine in listing.get("medicines", [])]
    return {
        "medicines": entries,
        "total": listing.get("total", 0),
        "page": listing.get("page", page),
        "limit": listing.get("limit", limit),
        "total_pages": listing.get("total_pages", 0),
    }


def medicine_brands(engine: Engine) -> list:
    """Returns all medicine brands for dropdowns / filters."""
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, name, manufacturer, contact_email, contact_phone "
                    "FROM brands ORDER BY name ASC"
                )
            ).mappings().all()
            return [dict(row) for row in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching brands.",
        ) from exc


# ---------------------------------------------------------------------------
# Category & brand CRUD
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Generates a URL-friendly slug from a free-text name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "category"


def medicine_category_create(engine: Engine, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new medicine category.

    - Validates the category name is present (422 when missing).
    - Generates a slug from the name when none is supplied.
    - Rejects duplicates by name or slug with HTTP 409.

    Raises HTTP 422 for invalid payloads, HTTP 409 for duplicates, and HTTP 500
    for unexpected database errors.
    """
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category name is required.",
        )
    slug = str(payload.get("slug") or "").strip() or _slugify(name)
    if len(slug) > 255:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category slug must be at most 255 characters.",
        )
    description = payload.get("description")
    storage_temperature = payload.get("storage_temperature") or "Room Temperature"

    try:
        with engine.begin() as conn:
            duplicate = conn.execute(
                text(
                    "SELECT id FROM categories "
                    "WHERE LOWER(name) = LOWER(:name) OR LOWER(slug) = LOWER(:slug)"
                ),
                {"name": name, "slug": slug},
            ).first()
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Category already exists with this name or slug.",
                )

            category_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO categories "
                    "(id, name, slug, description, storage_temperature) "
                    "VALUES (:id, :name, :slug, :description, :storage_temperature)"
                ),
                {
                    "id": category_id,
                    "name": name,
                    "slug": slug,
                    "description": description,
                    "storage_temperature": storage_temperature,
                },
            )

            row = conn.execute(
                text(
                    "SELECT c.id, c.name, c.slug, c.description, c.storage_temperature, "
                    "c.created_at, c.updated_at FROM categories c WHERE c.id = :category_id"
                ),
                {"category_id": category_id},
            ).mappings().first()

            return dict(row)
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category already exists with this name or slug.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the category.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the category.",
        ) from exc


def medicine_category_update(engine: Engine, category_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Partially updates a medicine category.

    - Raises HTTP 404 when the category is missing.
    - Validates the new name (422 when empty) and rejects duplicates by
      name or slug with HTTP 409.
    - Updates only the supplied fields (name, slug, description, storage_temperature).
    """
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM categories WHERE id = :category_id"),
                {"category_id": category_id},
            ).first()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

            updates: Dict[str, Any] = {}
            if "name" in payload and payload["name"] is not None:
                new_name = str(payload["name"]).strip()
                if not new_name:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Category name is required.")
                updates["name"] = new_name

            if "slug" in payload and payload["slug"] is not None:
                new_slug = str(payload["slug"]).strip()
                if not new_slug and "name" in updates:
                    new_slug = _slugify(updates["name"])
                if new_slug:
                    updates["slug"] = new_slug

            # Check duplicate by name or slug if either is being changed
            if "name" in updates or "slug" in updates:
                new_name = updates.get("name")
                new_slug = updates.get("slug")
                if new_name and new_slug:
                    duplicate = conn.execute(
                        text(
                            "SELECT id FROM categories "
                            "WHERE (LOWER(name) = LOWER(:dup_name) OR LOWER(slug) = LOWER(:dup_slug)) AND id <> :category_id"
                        ),
                        {"dup_name": new_name, "dup_slug": new_slug, "category_id": category_id},
                    ).first()
                elif new_name:
                    duplicate = conn.execute(
                        text("SELECT id FROM categories WHERE LOWER(name) = LOWER(:dup_name) AND id <> :category_id"),
                        {"dup_name": new_name, "category_id": category_id},
                    ).first()
                else:
                    duplicate = conn.execute(
                        text("SELECT id FROM categories WHERE LOWER(slug) = LOWER(:dup_slug) AND id <> :category_id"),
                        {"dup_slug": new_slug, "category_id": category_id},
                    ).first()
                if duplicate:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Category already exists with this name or slug.",
                    )

            if "description" in payload:
                updates["description"] = payload["description"]
            if "storage_temperature" in payload:
                updates["storage_temperature"] = payload["storage_temperature"]

            if updates:
                set_clause = ", ".join(f"{column} = :{column}" for column in updates)
                conn.execute(
                    text(f"UPDATE categories SET {set_clause} WHERE id = :category_id"),
                    {**updates, "category_id": category_id},
                )

            row = conn.execute(
                text(
                    "SELECT c.id, c.name, c.slug, c.description, c.storage_temperature, "
                    "c.created_at, c.updated_at FROM categories c WHERE c.id = :category_id"
                ),
                {"category_id": category_id},
            ).mappings().first()

            return dict(row)
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category already exists with this name or slug.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the category.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while updating the category.") from exc


def medicine_category_delete(engine: Engine, category_id: str) -> Dict[str, Any]:
    """
    Deletes a medicine category.

    - Raises HTTP 404 when the category is missing.
    - Raises HTTP 409 when medicines still reference the category.
    """
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM categories WHERE id = :category_id"),
                {"category_id": category_id},
            ).first()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

            referenced = conn.execute(
                text("SELECT id FROM medicines WHERE category_id = :category_id LIMIT 1"),
                {"category_id": category_id},
            ).first()
            if referenced:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete category: medicines are still assigned to it.",
                )

            conn.execute(
                text("DELETE FROM categories WHERE id = :category_id"),
                {"category_id": category_id},
            )
            return {"id": category_id, "deleted": True}
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1451:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete category: medicines are still assigned to it.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting the category.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while deleting the category.") from exc


def medicine_brand_create(engine: Engine, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a new medicine brand.

    - Validates the brand name is present (422 when missing).
    - Rejects duplicates by name with HTTP 409.

    Raises HTTP 422 for invalid payloads, HTTP 409 for duplicates, and HTTP 500
    for unexpected database errors.
    """
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Brand name is required.")

    manufacturer = payload.get("manufacturer")
    contact_email = payload.get("contact_email")
    contact_phone = payload.get("contact_phone")

    try:
        with engine.begin() as conn:
            duplicate = conn.execute(
                text("SELECT id FROM brands WHERE LOWER(name) = LOWER(:name)"),
                {"name": name},
            ).first()
            if duplicate:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Brand already exists with this name.")

            brand_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO brands "
                    "(id, name, manufacturer, contact_email, contact_phone) "
                    "VALUES (:id, :name, :manufacturer, :contact_email, :contact_phone)"
                ),
                {
                    "id": brand_id,
                    "name": name,
                    "manufacturer": manufacturer,
                    "contact_email": contact_email,
                    "contact_phone": contact_phone,
                },
            )

            row = conn.execute(
                text(
                    "SELECT b.id, b.name, b.manufacturer, b.contact_email, b.contact_phone, "
                    "b.created_at, b.updated_at FROM brands b WHERE b.id = :brand_id"
                ),
                {"brand_id": brand_id},
            ).mappings().first()

            return dict(row)
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1062:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Brand already exists with this name.") from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while creating the brand.") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while creating the brand.") from exc


def medicine_brand_update(engine: Engine, brand_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Partially updates a medicine brand.

    - Raises HTTP 404 when the brand is missing.
    - Validates the new name (422 when empty) and rejects duplicates with HTTP 409.
    - Updates only the supplied fields (name, manufacturer, contact_email, contact_phone).
    """
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM brands WHERE id = :brand_id"),
                {"brand_id": brand_id},
            ).first()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

            updates: Dict[str, Any] = {}
            if payload.get("name") is not None:
                new_name = str(payload.get("name")).strip()
                if not new_name:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Brand name is required.")
                duplicate = conn.execute(
                    text("SELECT id FROM brands WHERE LOWER(name) = LOWER(:name) AND id <> :brand_id"),
                    {"name": new_name, "brand_id": brand_id},
                ).first()
                if duplicate:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Brand already exists with this name.")
                updates["name"] = new_name
            if payload.get("manufacturer") is not None:
                updates["manufacturer"] = payload.get("manufacturer")
            if payload.get("contact_email") is not None:
                updates["contact_email"] = payload.get("contact_email")
            if payload.get("contact_phone") is not None:
                updates["contact_phone"] = payload.get("contact_phone")

            if updates:
                set_clause = ", ".join(f"{column} = :{column}" for column in updates)
                conn.execute(
                    text(f"UPDATE brands SET {set_clause} WHERE id = :brand_id"),
                    {**updates, "brand_id": brand_id},
                )

            row = conn.execute(
                text(
                    "SELECT b.id, b.name, b.manufacturer, b.contact_email, b.contact_phone, "
                    "b.created_at, b.updated_at FROM brands b WHERE b.id = :brand_id"
                ),
                {"brand_id": brand_id},
            ).mappings().first()

            return dict(row)
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1062:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Brand already exists with this name.") from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while updating the brand.") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while updating the brand.") from exc


def medicine_brand_delete(engine: Engine, brand_id: str) -> Dict[str, Any]:
    """
    Deletes a medicine brand.

    - Raises HTTP 404 when the brand is missing.
    - Raises HTTP 409 when medicines still reference the brand.
    """
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM brands WHERE id = :brand_id"),
                {"brand_id": brand_id},
            ).first()
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

            referenced = conn.execute(
                text("SELECT id FROM medicines WHERE brand_id = :brand_id LIMIT 1"),
                {"brand_id": brand_id},
            ).first()
            if referenced:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete brand: medicines are still assigned to it.")

            conn.execute(
                text("DELETE FROM brands WHERE id = :brand_id"),
                {"brand_id": brand_id},
            )
            return {"id": brand_id, "deleted": True}
    except HTTPException:
        raise
    except IntegrityError as exc:
        orig = getattr(exc, "orig", None)
        error_code = None
        orig_args = getattr(orig, "args", None)
        if orig_args:
            try:
                error_code = int(orig_args[0])
            except (TypeError, ValueError, IndexError):
                error_code = None
        if error_code == 1451:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete brand: medicines are still assigned to it.") from exc
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while deleting the brand.") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred while deleting the brand.") from exc


def medicine_batch_list(
    engine: Engine,
    search: str = "",
    medicine_id: str = "",
    status_filter: str = "",
    page: int = 1,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Lists medicine batches with filtering by search, medicine_id, and status.
    """
    safe_page = max(1, page)
    safe_limit = max(1, min(100, limit))
    offset = (safe_page - 1) * safe_limit

    conditions = []
    params: Dict[str, Any] = {"limit": safe_limit, "offset": offset}

    if search.strip():
        conditions.append("(b.batch_no LIKE :search OR m.name LIKE :search)")
        params["search"] = f"%{search.strip()}%"

    if medicine_id.strip():
        conditions.append("b.medicine_id = :medicine_id")
        params["medicine_id"] = medicine_id.strip()

    now_sql = "CURRENT_DATE()"
    if status_filter == "expired":
        conditions.append(f"b.expiry_date < {now_sql}")
    elif status_filter == "expiring_soon":
        conditions.append(f"b.expiry_date >= {now_sql} AND b.expiry_date <= DATE_ADD({now_sql}, INTERVAL 90 DAY)")
    elif status_filter == "low_stock":
        conditions.append("b.current_quantity <= 10")
    elif status_filter == "in_stock":
        conditions.append("b.current_quantity > 0")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    try:
        with engine.begin() as conn:
            total_count = conn.execute(
                text(
                    f"SELECT COUNT(*) FROM batches b "
                    f"LEFT JOIN medicines m ON b.medicine_id = m.id "
                    f"{where_clause}"
                ),
                params,
            ).scalar() or 0

            rows = conn.execute(
                text(
                    f"SELECT b.id, b.medicine_id, m.name AS medicine_name, m.dosage_form, m.unit, "
                    f"b.batch_no, b.mfg_date, b.expiry_date, b.purchase_cost, b.mrp, b.selling_price, "
                    f"b.initial_quantity, b.current_quantity, b.supplier_id, s.name AS supplier_name, "
                    f"b.created_at, b.updated_at "
                    f"FROM batches b "
                    f"LEFT JOIN medicines m ON b.medicine_id = m.id "
                    f"LEFT JOIN suppliers s ON b.supplier_id = s.id "
                    f"{where_clause} "
                    f"ORDER BY b.expiry_date ASC, b.created_at DESC "
                    f"LIMIT :limit OFFSET :offset"
                ),
                params,
            ).mappings().all()

            batches = [dict(row) for row in rows]
            total_pages = max(1, (total_count + safe_limit - 1) // safe_limit) if total_count > 0 else 1

            return {
                "batches": batches,
                "total": total_count,
                "page": safe_page,
                "limit": safe_limit,
                "total_pages": total_pages,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing batches.",
        ) from exc
