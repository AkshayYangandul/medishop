"""
MediShop medicine & inventory endpoint tests
===========================================
Offline unit tests for the medicine catalogue and inventory service layer.

These tests invoke the service functions directly with mock SQLAlchemy engine
connections (``unittest.mock.MagicMock``), so no HTTP layer or live MySQL
database is required.

Covered behaviours:
- Medicine listing (pagination + response envelope).
- Medicine retrieval (found / missing).
- Medicine creation (success / invalid category / invalid dosage form).
- Medicine update incl. deactivation via ``is_active``.
- Inventory retrieval (stock + batches) and missing medicine.
"""

import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


def _import_medicine_service():
    try:
        import medicine_service as service
    except ImportError:
        import backend.medicine_service as service
    return service


def _import_main():
    try:
        import main as main_mod
    except ImportError:
        import backend.main as main_mod
    return main_mod


medicine_service = _import_medicine_service()
main = _import_main()


def _make_engine_with_conn(conn=None):
    """Returns a mock engine whose context-manager (engine.begin) yields ``conn``."""
    if conn is None:
        conn = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    engine.begin.return_value.__exit__.return_value = False
    return engine


MEDICINE_ROW = {
    "id": "med-1",
    "name": "Paracetamol 650mg",
    "generic_name": "Paracetamol",
    "dosage_form": "Tablet",
    "strength": "650mg",
    "unit": "Strip",
    "hsn_code": "3004",
    "requires_prescription": False,
    "min_stock_alert": 10,
    "is_active": True,
    "created_at": None,
    "updated_at": None,
    "category_id": "cat-1",
    "category_name": "Analgesics",
    "brand_id": "brand-1",
    "brand_name": "Dr. Reddy's Lab",
}


class TestMedicineService(unittest.TestCase):
    """Tests for medicine catalogue + inventory service layer."""

    # ------------------------------------------------------------------
    # Medicine list
    # ------------------------------------------------------------------

    def _conn_with_medicine_rows(self, rows, total):
        conn = MagicMock()

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "COUNT(*)" in sql:
                result.scalar_one.return_value = total
            elif "FROM medicines m" in sql and "COUNT(*)" not in sql:
                result.mappings.return_value.all.return_value = rows
            else:
                result.mappings.return_value.all.return_value = rows
            return result

        conn.execute.side_effect = _execute
        return conn

    def test_medicine_list_returns_paginated_response(self):
        conn = self._conn_with_medicine_rows([MEDICINE_ROW, {**MEDICINE_ROW, "id": "med-2", "name": "Ibuprofen 400mg"}], total=2)

        result = medicine_service.medicine_list(
            _make_engine_with_conn(conn),
            search="",
            category_id="",
            brand_id="",
            is_active=True,
            page=1,
            limit=20,
        )

        self.assertEqual(len(result["medicines"]), 2)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["limit"], 20)
        self.assertEqual(result["total_pages"], 1)

    def test_medicine_list_computes_total_pages(self):
        conn = self._conn_with_medicine_rows([], total=25)
        result = medicine_service.medicine_list(
            _make_engine_with_conn(conn),
            search="",
            category_id="",
            brand_id="",
            is_active=True,
            page=2,
            limit=10,
        )
        self.assertEqual(result["total"], 25)
        self.assertEqual(result["total_pages"], 3)

    # ------------------------------------------------------------------
    # Medicine get
    # ------------------------------------------------------------------

    def test_medicine_get_found(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = MEDICINE_ROW
        result = medicine_service.medicine_get(_make_engine_with_conn(conn), "med-1")
        self.assertEqual(result["id"], "med-1")
        self.assertEqual(result["name"], "Paracetamol 650mg")

    def test_medicine_get_missing_raises_404(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_get(_make_engine_with_conn(conn), "med-missing")
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # Medicine create
    # ------------------------------------------------------------------

    def _conn_for_create(self):
        conn = MagicMock()

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "SELECT id FROM categories" in sql:
                result.first.return_value = {"id": "cat-1"}
            elif "INSERT INTO medicines" in sql:
                return MagicMock()
            elif "SELECT m.id, m.name" in sql:
                result.mappings.return_value.first.return_value = MEDICINE_ROW
            return result

        conn.execute.side_effect = _execute
        return conn

    def test_medicine_create_success(self):
        result = medicine_service.medicine_create(
            _make_engine_with_conn(self._conn_for_create()),
            {
                "name": "Paracetamol 650mg",
                "generic_name": "Paracetamol",
                "category_id": "cat-1",
                "brand_id": "brand-1",
                "dosage_form": "Tablet",
                "strength": "650mg",
                "unit": "Strip",
                "hsn_code": "3004",
                "requires_prescription": False,
                "min_stock_alert": 10,
                "is_active": True,
            },
        )
        self.assertEqual(result["id"], "med-1")

    def test_medicine_create_invalid_category_raises_422(self):
        conn = MagicMock()
        conn.execute.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_create(
                _make_engine_with_conn(conn),
                {
                    "name": "Paracetamol 650mg",
                    "category_id": "missing-cat",
                    "dosage_form": "Tablet",
                },
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_medicine_create_invalid_dosage_form_raises_422(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_create(
                _make_engine_with_conn(MagicMock()),
                {
                    "name": "Bad Medicine",
                    "category_id": "cat-1",
                    "dosage_form": "NotADosage",
                },
            )
        self.assertEqual(ctx.exception.status_code, 422)

    # ------------------------------------------------------------------
    # Medicine update (incl. deactivation)
    # ------------------------------------------------------------------

    def test_medicine_update_deactivates_medicine(self):
        conn = MagicMock()
        conn.execute.return_value.first.return_value = {"id": "med-1"}

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "SELECT m.id, m.name" in sql:
                result.mappings.return_value.first.return_value = {
                    **MEDICINE_ROW,
                    "is_active": False,
                }
            return result

        conn.execute.side_effect = _execute

        result = medicine_service.medicine_update(
            _make_engine_with_conn(conn),
            "med-1",
            {"is_active": False},
        )
        self.assertFalse(result["is_active"])

    def test_medicine_update_missing_raises_404(self):
        conn = MagicMock()
        conn.execute.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_update(_make_engine_with_conn(conn), "med-missing", {"name": "X"})
        self.assertEqual(ctx.exception.status_code, 404)

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    def test_medicine_inventory_returns_stock_and_batches(self):
        medicine_row = {
            "id": "med-1",
            "name": "Paracetamol 650mg",
            "min_stock_alert": 10,
            "is_active": True,
        }
        conn = MagicMock()
        stock_result = MagicMock()
        stock_result.__getitem__.return_value = 5
        batch_row = {
            "id": "bat-1",
            "batch_no": "BAT-2026-001",
            "expiry_date": None,
            "current_quantity": 5,
        }

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "COALESCE(SUM" in sql:
                result.first.return_value.__getitem__.return_value = 5
            elif "FROM batches b" in sql:
                result.mappings.return_value.all.return_value = [batch_row]
            elif "FROM medicines m WHERE m.id" in sql:
                result.mappings.return_value.first.return_value = medicine_row
            return result

        conn.execute.side_effect = _execute
        result = medicine_service.medicine_inventory(_make_engine_with_conn(conn), "med-1")
        self.assertEqual(result["medicine_id"], "med-1")
        self.assertEqual(result["current_stock"], 5)
        self.assertTrue(result["is_low_stock"])
        self.assertEqual(len(result["batches"]), 1)

    def test_medicine_inventory_missing_raises_404(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_inventory(_make_engine_with_conn(conn), "med-missing")
        self.assertEqual(ctx.exception.status_code, 404)


class TestMedicineBatchCreate(unittest.TestCase):
    """Tests for POST /api/batches medicine batch creation service logic."""

    BATCH_ROW = {
        "id": "bat-1",
        "medicine_id": "med-1",
        "batch_no": "BAT-2026-001",
        "mfg_date": date(2026, 1, 15),
        "expiry_date": date(2026, 12, 31),
        "purchase_cost": Decimal("100.55"),
        "mrp": Decimal("149.99"),
        "selling_price": Decimal("120.00"),
        "initial_quantity": 10,
        "current_quantity": 10,
        "supplier_id": "sup-1",
        "supplier_name": "Sun Pharma Ltd",
    }

    BATCH_PAYLOAD = {
        "medicine_id": "med-1",
        "batch_no": "BAT-2026-001",
        "mfg_date": date(2026, 1, 15),
        "expiry_date": date(2026, 12, 31),
        "purchase_cost": Decimal("100.55"),
        "mrp": Decimal("149.99"),
        "selling_price": Decimal("120.00"),
        "initial_quantity": 10,
        "supplier_id": "sup-1",
    }

    MEDICINES = {
        "med-1": {"id": "med-1"},
        "med-missing": None,
    }

    SUPPLIERS = {
        "sup-1": {"id": "sup-1"},
        "sup-missing": None,
    }

    def _conn_for_batch(self):
        conn = MagicMock()

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "SELECT id FROM medicines" in sql:
                result.first.return_value = self.MEDICINES.get(params.get("medicine_id"))
            elif "SELECT id FROM suppliers" in sql:
                result.first.return_value = self.SUPPLIERS.get(params.get("id")) if params.get("id") else None
            elif "SELECT id FROM batches" in sql:
                result.first.return_value = None
            elif "INSERT INTO batches" in sql:
                return MagicMock()
            elif "SELECT b.id, b.medicine_id" in sql:
                result.mappings.return_value.first.return_value = self.BATCH_ROW
            return result

        conn.execute.side_effect = _execute
        return conn

    def test_batch_create_success_sets_initial_and_current_quantity(self):
        """A valid batch is created; initial_quantity and current_quantity match."""
        result = medicine_service.medicine_batch_create(
            _make_engine_with_conn(self._conn_for_batch()),
            dict(self.BATCH_PAYLOAD),
        )

        self.assertEqual(result["batch_no"], "BAT-2026-001")
        self.assertEqual(result["medicine_id"], "med-1")
        self.assertEqual(result["initial_quantity"], 10)
        self.assertEqual(result["current_quantity"], 10)
        self.assertEqual(result["purchase_cost"], Decimal("100.55"))
        self.assertEqual(result["mrp"], Decimal("149.99"))
        self.assertEqual(result["selling_price"], Decimal("120.00"))

    def test_batch_create_missing_medicine_returns_404(self):
        payload = dict(self.BATCH_PAYLOAD, medicine_id="med-missing")
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_batch_create(_make_engine_with_conn(self._conn_for_batch()), payload)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_batch_create_missing_supplier_returns_422(self):
        payload = dict(self.BATCH_PAYLOAD, supplier_id="sup-missing")
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_batch_create(_make_engine_with_conn(self._conn_for_batch()), payload)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_batch_create_mfg_after_expiry_returns_422(self):
        payload = dict(
            self.BATCH_PAYLOAD,
            mfg_date=date(2026, 12, 31),
            expiry_date=date(2026, 12, 30),
        )
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_batch_create(_make_engine_with_conn(self._conn_for_batch()), payload)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_batch_create_selling_price_above_mrp_returns_422(self):
        payload = dict(self.BATCH_PAYLOAD, selling_price=Decimal("200"), mrp=Decimal("150"))
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_batch_create(_make_engine_with_conn(self._conn_for_batch()), payload)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_batch_create_duplicate_batch_returns_409(self):
        conn = MagicMock()
        conn.execute.return_value.first.return_value = {"id": "bat-1"}

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "SELECT id FROM batches" in sql:
                result.first.return_value = {"id": "bat-1"}
            elif "SELECT b.id, b.medicine_id" in sql:
                result.mappings.return_value.first.return_value = self.BATCH_ROW
            return result

        conn.execute.side_effect = _execute
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_batch_create(_make_engine_with_conn(conn), dict(self.BATCH_PAYLOAD))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_batch_create_negative_values_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            main.BatchCreateRequest(
                medicine_id="med-1",
                batch_no="BAT-2026-001",
                expiry_date=date(2026, 12, 31),
                purchase_cost=Decimal("-1"),
                mrp=Decimal("150"),
                selling_price=Decimal("125"),
                initial_quantity=10,
            )
        with self.assertRaises(ValidationError):
            main.BatchCreateRequest(
                medicine_id="med-1",
                batch_no="BAT-2026-002",
                expiry_date=date(2026, 12, 31),
                purchase_cost=Decimal("100"),
                mrp=Decimal("150"),
                selling_price=Decimal("-5"),
                initial_quantity=10,
            )
        with self.assertRaises(ValidationError):
            main.BatchCreateRequest(
                medicine_id="med-1",
                batch_no="BAT-2026-003",
                expiry_date=date(2026, 12, 31),
                purchase_cost=Decimal("100"),
                mrp=Decimal("150"),
                selling_price=Decimal("125"),
                initial_quantity=-3,
            )

    def test_batch_create_other_integrity_failure_returns_generic_error(self):
        """Non-duplicate integrity failures must not surface as a batch 409."""
        conn = MagicMock()

        def _execute(stmt, params=None):
            sql = str(stmt)
            if "INSERT INTO batches" in sql:
                raise IntegrityError("INSERT INTO batches", {}, Exception("check constraint violation"))
            result = MagicMock()
            sql_lower = sql.lower()
            if "medicines" in sql_lower:
                result.first.return_value = {"id": "med-1"}
            elif "suppliers" in sql_lower:
                result.first.return_value = {"id": "sup-1"}
            elif "batches" in sql_lower:
                result.first.return_value = None
            return result

        conn.execute.side_effect = _execute
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_batch_create(_make_engine_with_conn(conn), dict(self.BATCH_PAYLOAD))
        self.assertEqual(ctx.exception.status_code, 500)


class TestMedicineCategoryCrud(unittest.TestCase):
    """Tests for category CRUD service logic (POST/PUT/DELETE /api/categories)."""

    CATEGORY_ROW = {
        "id": "cat-1",
        "name": "Analgesics",
        "slug": "analgesics",
        "description": None,
        "storage_temperature": "Room Temperature",
        "created_at": "2026-01-01 00:00:00",
        "updated_at": "2026-01-01 00:00:00",
    }

    def _conn(self, existing=None, duplicate=None, referenced=None, insert_error=None):
        conn = MagicMock()
        state = {"existing": existing, "duplicate": duplicate, "referenced": referenced}

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            result.first.return_value = None
            if "INSERT INTO categories" in sql:
                if insert_error is not None:
                    raise insert_error
                return MagicMock()
            if "SELECT c.id, c.name, c.slug" in sql:
                result.mappings.return_value.first.return_value = self.CATEGORY_ROW
            elif "SELECT id FROM categories WHERE id = :category_id" in sql:
                result.first.return_value = state["existing"]
            elif "SELECT id FROM categories WHERE LOWER(name)" in sql or "(LOWER(name) = LOWER(:name)" in sql:
                result.first.return_value = state["duplicate"]
            elif "DELETE FROM categories" in sql:
                return MagicMock()
            elif "FROM medicines WHERE category_id" in sql:
                result.first.return_value = state["referenced"]
            return result

        conn.execute.side_effect = _execute
        return conn

    def test_medicine_category_create_success(self):
        result = medicine_service.medicine_category_create(
            _make_engine_with_conn(self._conn()),
            {"name": "Analgesics", "slug": "analgesics", "description": None, "storage_temperature": "Room Temperature"},
        )
        self.assertEqual(result["id"], "cat-1")
        self.assertEqual(result["name"], "Analgesics")
        self.assertEqual(result["slug"], "analgesics")

    def test_medicine_category_create_duplicate_returns_409(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_create(
                _make_engine_with_conn(self._conn(duplicate={"id": "cat-1"})),
                {"name": "Analgesics", "slug": "analgesics", "description": None, "storage_temperature": "Room Temperature"},
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_medicine_category_create_missing_name_returns_422(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_create(
                _make_engine_with_conn(),
                {"name": "   ", "slug": None, "description": None, "storage_temperature": None},
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_medicine_category_create_database_error_returns_generic_error(self):
        conn = MagicMock()

        def _execute(stmt, params=None):
            if "INSERT INTO categories" in str(stmt):
                raise RuntimeError("simulated db failure")
            result = MagicMock()
            result.first.return_value = None
            if "SELECT c.id, c.name, c.slug" in str(stmt):
                result.mappings.return_value.first.return_value = self.CATEGORY_ROW
            return result

        conn.execute.side_effect = _execute
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_create(_make_engine_with_conn(conn), {"name": "New Category"})
        self.assertEqual(ctx.exception.status_code, 500)

    def test_medicine_category_update_missing_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_update(_make_engine_with_conn(self._conn(existing=None)), "cat-missing", {"description": "Pain relief"})
        self.assertEqual(ctx.exception.status_code, 404)

    def test_medicine_category_update_duplicate_returns_409(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_update(_make_engine_with_conn(self._conn(existing={"id": "cat-1"}, duplicate={"id": "cat-2"})), "cat-1", {"name": "Analgesics"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_medicine_category_update_success(self):
        result = medicine_service.medicine_category_update(
            _make_engine_with_conn(self._conn(existing={"id": "cat-1"})),
            "cat-1",
            {"name": "Analgesics", "description": "Pain relief", "storage_temperature": "Room Temperature"},
        )
        self.assertEqual(result["id"], "cat-1")
        self.assertEqual(result["name"], "Analgesics")
        self.assertEqual(result["slug"], "analgesics")

    def test_medicine_category_delete_blocked_when_referenced_returns_409(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_delete(_make_engine_with_conn(self._conn(existing={"id": "cat-1"}, referenced={"id": "med-1"})), "cat-1")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_medicine_category_delete_missing_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_category_delete(_make_engine_with_conn(self._conn(existing=None)), "cat-missing")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_medicine_category_delete_success(self):
        result = medicine_service.medicine_category_delete(_make_engine_with_conn(self._conn(existing={"id": "cat-1"}, referenced=None)), "cat-1")
        self.assertTrue(result["deleted"])


class TestMedicineBrandCrud(unittest.TestCase):
    """Tests for brand CRUD service logic (POST/PUT/DELETE /api/brands)."""

    BRAND_ROW = {
        "id": "brand-1",
        "name": "Sun Pharma",
        "manufacturer": "Sun Pharma Ltd",
        "contact_email": "sales@sunpharma.example",
        "contact_phone": "+91-22-12345678",
        "created_at": "2026-01-01 00:00:00",
        "updated_at": "2026-01-01 00:00:00",
    }

    def _conn(self, existing=None, duplicate=None, referenced=None, insert_error=None):
        conn = MagicMock()
        state = {"existing": existing, "duplicate": duplicate, "referenced": referenced}

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            result.first.return_value = None
            if "INSERT INTO brands" in sql:
                if insert_error is not None:
                    raise insert_error
                return MagicMock()
            if "SELECT b.id, b.name, b.manufacturer" in sql:
                result.mappings.return_value.first.return_value = self.BRAND_ROW
            elif "SELECT id FROM brands WHERE id = :brand_id" in sql:
                result.first.return_value = state["existing"]
            elif "SELECT id FROM brands WHERE LOWER(name)" in sql:
                result.first.return_value = state["duplicate"]
            elif "DELETE FROM brands" in sql:
                return MagicMock()
            elif "FROM medicines WHERE brand_id" in sql:
                result.first.return_value = state["referenced"]
            return result

        conn.execute.side_effect = _execute
        return conn

    def test_medicine_brand_create_success(self):
        result = medicine_service.medicine_brand_create(
            _make_engine_with_conn(self._conn()),
            {"name": "Sun Pharma", "manufacturer": "Sun Pharma Ltd", "contact_email": "sales@sunpharma.example", "contact_phone": "+91-22-12345678"},
        )
        self.assertEqual(result["id"], "brand-1")
        self.assertEqual(result["name"], "Sun Pharma")

    def test_medicine_brand_create_duplicate_returns_409(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_create(_make_engine_with_conn(self._conn(duplicate={"id": "brand-1"})), {"name": "Sun Pharma"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_medicine_brand_create_missing_name_returns_422(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_create(_make_engine_with_conn(), {"name": "  "})
        self.assertEqual(ctx.exception.status_code, 422)

    def test_medicine_brand_create_database_error_returns_generic_error(self):
        conn = MagicMock()

        def _execute(stmt, params=None):
            if "INSERT INTO brands" in str(stmt):
                raise RuntimeError("simulated db failure")
            result = MagicMock()
            result.first.return_value = None
            if "SELECT b.id, b.name, b.manufacturer" in str(stmt):
                result.mappings.return_value.first.return_value = self.BRAND_ROW
            return result

        conn.execute.side_effect = _execute
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_create(_make_engine_with_conn(conn), {"name": "New Brand"})
        self.assertEqual(ctx.exception.status_code, 500)

    def test_medicine_brand_update_missing_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_update(_make_engine_with_conn(self._conn(existing=None)), "brand-missing", {"name": "Sun Pharma"})
        self.assertEqual(ctx.exception.status_code, 404)

    def test_medicine_brand_update_duplicate_returns_409(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_update(_make_engine_with_conn(self._conn(existing={"id": "brand-1"}, duplicate={"id": "brand-2"})), "brand-1", {"name": "Sun Pharma"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_medicine_brand_update_success(self):
        result = medicine_service.medicine_brand_update(_make_engine_with_conn(self._conn(existing={"id": "brand-1"})), "brand-1", {"name": "Sun Pharma", "manufacturer": "Updated Manufacturer"})
        self.assertEqual(result["id"], "brand-1")
        self.assertEqual(result["name"], "Sun Pharma")

    def test_medicine_brand_delete_blocked_when_referenced_returns_409(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_delete(_make_engine_with_conn(self._conn(existing={"id": "brand-1"}, referenced={"id": "med-1"})), "brand-1")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_medicine_brand_delete_missing_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            medicine_service.medicine_brand_delete(_make_engine_with_conn(self._conn(existing=None)), "brand-missing")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_medicine_brand_delete_success(self):
        result = medicine_service.medicine_brand_delete(_make_engine_with_conn(self._conn(existing={"id": "brand-1"}, referenced=None)), "brand-1")
        self.assertTrue(result["deleted"])


class TestMedicineCatalogReadAndAdminAccess(unittest.TestCase):
    """Tests for category/brand listing, admin write gating, and schema validation."""

    def test_medicine_categories_list_returns_rows(self):
        conn = MagicMock()

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "SELECT id, name, slug, description, storage_temperature FROM categories" in sql:
                result.mappings.return_value.all.return_value = [TestMedicineCategoryCrud.CATEGORY_ROW]
            else:
                result.first.return_value = None
            return result

        conn.execute.side_effect = _execute
        result = medicine_service.medicine_categories(_make_engine_with_conn(conn))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Analgesics")

    def test_medicine_brands_list_returns_rows(self):
        conn = MagicMock()

        def _execute(stmt, params=None):
            sql = str(stmt)
            result = MagicMock()
            if "SELECT id, name, manufacturer, contact_email, contact_phone FROM brands" in sql:
                result.mappings.return_value.all.return_value = [TestMedicineBrandCrud.BRAND_ROW]
            else:
                result.first.return_value = None
            return result

        conn.execute.side_effect = _execute
        result = medicine_service.medicine_brands(_make_engine_with_conn(conn))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Sun Pharma")

    def test_medicine_categories_write_requires_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            main.require_active_admin(current_user={"id": "u1", "role": "pharmacist", "is_active": True})
        self.assertEqual(ctx.exception.status_code, 403)

        admin_result = main.require_active_admin(current_user={"id": "u1", "role": "admin", "is_active": True})
        self.assertEqual(admin_result["role"], "admin")

    def test_medicine_brands_write_requires_admin(self):
        with self.assertRaises(HTTPException) as ctx:
            main.require_active_admin(current_user={"id": "u1", "role": "pharmacist", "is_active": True})
        self.assertEqual(ctx.exception.status_code, 403)

        admin_result = main.require_active_admin(current_user={"id": "u1", "role": "admin", "is_active": True})
        self.assertEqual(admin_result["role"], "admin")

    def test_medicine_category_create_missing_name_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            main.CategoryCreateRequest(slug="analgesics", description=None, storage_temperature="Room Temperature")

    def test_medicine_brand_create_missing_name_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            main.BrandCreateRequest(manufacturer=None, contact_email=None, contact_phone=None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
