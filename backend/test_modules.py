"""
Unit tests for MediShop Expanded Modules
=========================================
Tests for suppliers, customers, sales invoices, inward purchases,
operating expenses, batch listing, user administration, and reports.
"""

import unittest
from unittest.mock import MagicMock
from decimal import Decimal
from fastapi import HTTPException

try:
    import sales_service
    import user_service
    import medicine_service
except ImportError:
    from backend import sales_service
    from backend import user_service
    from backend import medicine_service


def _make_mock_engine(conn=None):
    if conn is None:
        conn = MagicMock()
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    return engine, conn


class TestSuppliersService(unittest.TestCase):
    def test_supplier_list(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.mappings.return_value.all.return_value = [
            {"id": "s-1", "name": "Apex Pharma", "phone": "1234567890"}
        ]
        result = sales_service.supplier_list(engine, search="Apex")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Apex Pharma")

    def test_supplier_create_missing_name_fails(self):
        engine, conn = _make_mock_engine()
        with self.assertRaises(HTTPException) as ctx:
            sales_service.supplier_create(engine, {"name": "", "phone": "1234567890"})
        self.assertEqual(ctx.exception.status_code, 422)

    def test_supplier_create_success(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "s-1",
            "name": "Apex Pharma",
            "phone": "1234567890",
            "contact_person": "Dr. Smith",
            "email": "apex@example.com",
            "address": "123 Health Ave",
            "gstin": "27ABCDE1234F1Z5",
            "drug_license_no": "DL-12345",
            "is_active": True,
        }
        res = sales_service.supplier_create(
            engine,
            {"name": "Apex Pharma", "phone": "1234567890", "contact_person": "Dr. Smith"}
        )
        self.assertEqual(res["id"], "s-1")
        self.assertEqual(res["name"], "Apex Pharma")

    def test_supplier_delete_blocked_by_purchases_fails(self):
        engine, conn = _make_mock_engine()
        conn.execute.side_effect = [
            MagicMock(first=MagicMock(return_value={"id": "s-1"})),  # exists
            MagicMock(first=MagicMock(return_value={"id": "pur-1"})),  # has purchases
        ]
        with self.assertRaises(HTTPException) as ctx:
            sales_service.supplier_delete(engine, "s-1")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("referenced by purchase records", ctx.exception.detail)


class TestCustomersService(unittest.TestCase):
    def test_customer_list(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.mappings.return_value.all.return_value = [
            {"id": "c-1", "name": "Jane Doe", "phone": "9876543210"}
        ]
        result = sales_service.customer_list(engine, search="Jane")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Jane Doe")

    def test_customer_create_success(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.first.return_value = None  # no existing phone
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "c-1",
            "name": "Jane Doe",
            "phone": "9876543210",
            "email": "jane@example.com",
            "address": "456 Elm St",
            "doctor_name": "Dr. House",
            "allergies_or_notes": "None",
        }
        res = sales_service.customer_create(
            engine,
            {"name": "Jane Doe", "phone": "9876543210"}
        )
        self.assertEqual(res["id"], "c-1")
        self.assertEqual(res["name"], "Jane Doe")

    def test_customer_update_phone_duplicate_fails(self):
        engine, conn = _make_mock_engine()
        conn.execute.side_effect = [
            MagicMock(mappings=MagicMock(return_value=MagicMock(first=MagicMock(return_value={"id": "c-1"})))),
            MagicMock(first=MagicMock(return_value={"id": "c-2"})),  # dup phone
        ]
        with self.assertRaises(HTTPException) as ctx:
            sales_service.customer_update(engine, "c-1", {"phone": "9999999999"})
        self.assertEqual(ctx.exception.status_code, 409)

    def test_customer_delete_success(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.first.return_value = {"id": "c-1"}
        res = sales_service.customer_delete(engine, "c-1")
        self.assertTrue(res["deleted"])


class TestInvoicesService(unittest.TestCase):
    def test_invoice_create_insufficient_stock_fails(self):
        engine, conn = _make_mock_engine()
        # Mock batch row with only 2 in stock
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "b-1",
            "medicine_id": "m-1",
            "current_quantity": 2,
            "selling_price": Decimal("10.00"),
            "mrp": Decimal("12.00"),
            "purchase_cost": Decimal("7.00"),
            "medicine_name": "Paracetamol 500mg",
        }

        payload = {
            "customer_id": None,
            "payment_method": "cash",
            "items": [
                {"medicine_id": "m-1", "batch_id": "b-1", "quantity": 10}
            ]
        }
        with self.assertRaises(HTTPException) as ctx:
            sales_service.invoice_create(engine, payload, created_by="user-1")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Insufficient stock", ctx.exception.detail)

    def test_invoice_create_success_records_ledger(self):
        engine, conn = _make_mock_engine()
        executed_sqls = []

        def _execute(stmt, params=None):
            sql = str(stmt)
            executed_sqls.append((sql, params))
            res = MagicMock()
            if "SELECT b.id, b.medicine_id" in sql:
                res.mappings.return_value.first.return_value = {
                    "id": "b-1",
                    "medicine_id": "m-1",
                    "current_quantity": 20,
                    "selling_price": Decimal("10.00"),
                    "mrp": Decimal("12.00"),
                    "purchase_cost": Decimal("7.00"),
                    "medicine_name": "Amoxicillin 500mg",
                }
            elif "SELECT i.id, i.invoice_no" in sql:
                res.mappings.return_value.first.return_value = {
                    "id": "inv-1",
                    "invoice_no": "INV-20261031-001",
                    "net_amount": Decimal("50.00"),
                    "payment_method": "cash",
                    "payment_status": "paid",
                    "customer_name": None,
                    "created_at": "2026-10-31T10:00:00",
                }
            elif "SELECT it.id, it.medicine_id" in sql:
                res.mappings.return_value.all.return_value = []
            return res

        conn.execute.side_effect = _execute

        payload = {
            "customer_id": None,
            "payment_method": "cash",
            "items": [
                {"medicine_id": "m-1", "batch_id": "b-1", "quantity": 5}
            ]
        }
        res = sales_service.invoice_create(engine, payload, created_by="user-1")
        self.assertEqual(res["id"], "inv-1")

        # Verify stock movement inserted with sale_out
        stock_movement_inserts = [
            (sql, params) for sql, params in executed_sqls
            if "INSERT INTO stock_movements" in sql
        ]
        self.assertEqual(len(stock_movement_inserts), 1)
        sm_params = stock_movement_inserts[0][1]
        self.assertEqual(sm_params["qty_change"], -5)
        self.assertEqual(sm_params["qty_before"], 20)
        self.assertEqual(sm_params["qty_after"], 15)


class TestPurchasesService(unittest.TestCase):
    def test_purchase_create_missing_supplier_fails(self):
        engine, conn = _make_mock_engine()
        with self.assertRaises(HTTPException) as ctx:
            sales_service.purchase_create(engine, {"supplier_id": ""})
        self.assertEqual(ctx.exception.status_code, 422)

    def test_purchase_create_invalid_dates_fails(self):
        engine, conn = _make_mock_engine()
        conn.execute.side_effect = [
            MagicMock(first=MagicMock(return_value={"id": "s-1"})),  # supplier exists
            MagicMock(first=MagicMock(return_value=None)),  # no duplicate invoice
        ]
        payload = {
            "supplier_id": "s-1",
            "invoice_no": "BILL-100",
            "items": [
                {
                    "medicine_id": "m-1",
                    "batch_no": "B1",
                    "mfg_date": "2026-12-01",
                    "expiry_date": "2026-05-01",  # mfg after expiry
                    "quantity": 10,
                    "unit_cost": 20,
                    "mrp": 30,
                    "selling_price": 25,
                }
            ]
        }
        with self.assertRaises(HTTPException) as ctx:
            sales_service.purchase_create(engine, payload, created_by="user-1")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("mfg_date must be earlier than expiry_date", ctx.exception.detail)

    def test_purchase_create_selling_price_exceeds_mrp_fails(self):
        engine, conn = _make_mock_engine()
        conn.execute.side_effect = [
            MagicMock(first=MagicMock(return_value={"id": "s-1"})),
            MagicMock(first=MagicMock(return_value=None)),
        ]
        payload = {
            "supplier_id": "s-1",
            "items": [
                {
                    "medicine_id": "m-1",
                    "batch_no": "B1",
                    "expiry_date": "2027-05-01",
                    "quantity": 10,
                    "unit_cost": 20,
                    "mrp": 30,
                    "selling_price": 40,  # exceeds mrp
                }
            ]
        }
        with self.assertRaises(HTTPException) as ctx:
            sales_service.purchase_create(engine, payload, created_by="user-1")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("cannot exceed MRP", ctx.exception.detail)


class TestExpensesService(unittest.TestCase):
    def test_expense_create_invalid_amount_fails(self):
        engine, conn = _make_mock_engine()
        with self.assertRaises(HTTPException) as ctx:
            sales_service.expense_create(engine, {"title": "Rent", "category": "Utilities", "amount": 0})
        self.assertEqual(ctx.exception.status_code, 422)

    def test_expense_create_success(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "exp-1",
            "title": "Shop Electricity",
            "category": "Utilities",
            "amount": Decimal("1500.00"),
            "expense_date": "2026-10-30",
            "payment_method": "cash",
            "receipt_url": None,
            "notes": "Paid in cash",
            "created_by": "user-1",
            "created_by_name": "Admin User",
            "created_at": "2026-10-30T10:00:00",
        }
        res = sales_service.expense_create(
            engine,
            {"title": "Shop Electricity", "category": "Utilities", "amount": 1500},
            created_by="user-1"
        )
        self.assertEqual(res["id"], "exp-1")
        self.assertEqual(res["title"], "Shop Electricity")


class TestUserAdminService(unittest.TestCase):
    def test_user_list(self):
        engine, conn = _make_mock_engine()
        conn.execute.return_value.mappings.return_value.all.return_value = [
            {"id": "u-1", "email": "admin@example.com", "role": "admin", "is_active": True}
        ]
        result = user_service.user_list(engine)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["email"], "admin@example.com")

    def test_user_create_invalid_email_fails(self):
        engine, conn = _make_mock_engine()
        with self.assertRaises(HTTPException) as ctx:
            user_service.user_create(engine, {"email": "invalid", "password": "secretpassword", "full_name": "Test"})
        self.assertEqual(ctx.exception.status_code, 422)


class TestBatchesService(unittest.TestCase):
    def test_medicine_batch_list(self):
        engine, conn = _make_mock_engine()
        conn.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),  # total
            MagicMock(mappings=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                {"id": "b-1", "batch_no": "B99", "medicine_name": "Paracetamol"}
            ])))),
        ]
        res = medicine_service.medicine_batch_list(engine, search="Paracetamol", status_filter="expiring_soon")
        self.assertEqual(res["total"], 1)
        self.assertEqual(len(res["batches"]), 1)
        self.assertEqual(res["batches"][0]["batch_no"], "B99")


class TestDashboardAndReports(unittest.TestCase):
    def test_dashboard_stats_success(self):
        engine, conn = _make_mock_engine()

        def _execute(stmt, params=None):
            sql = str(stmt)
            res = MagicMock()
            if "SELECT COALESCE(SUM(net_amount)" in sql:
                res.mappings.return_value.first.return_value = {"total_revenue": 5000.0, "tx_count": 12}
            elif "SELECT COUNT(*) FROM medicines WHERE is_active = TRUE" in sql:
                res.scalar.return_value = 45
            elif "low_stock_items" in sql:
                res.scalar.return_value = 3
            elif "batches" in sql and "expiry_date" in sql:
                res.scalar.return_value = 2
            elif "FROM categories c" in sql:
                res.mappings.return_value.all.return_value = [{"name": "Antibiotics", "medicine_count": 10}]
            elif "FROM invoices i" in sql:
                res.mappings.return_value.all.return_value = []
            elif "FROM invoices" in sql and "GROUP BY DATE(created_at)" in sql:
                res.mappings.return_value.all.return_value = []
            return res

        conn.execute.side_effect = _execute
        stats = sales_service.dashboard_stats(engine)
        self.assertEqual(stats["today_revenue"], 5000.0)
        self.assertEqual(stats["today_orders"], 12)
        self.assertEqual(stats["total_medicines"], 45)
        self.assertEqual(stats["low_stock_count"], 3)
        self.assertEqual(stats["expiring_batches_count"], 2)

    def test_reports_summary_computes_pnl(self):
        engine, conn = _make_mock_engine()

        def _execute(stmt, params=None):
            sql = str(stmt)
            res = MagicMock()
            if "SELECT " in sql and "total_revenue" in sql and "total_cogs" in sql:
                res.mappings.return_value.first.return_value = {
                    "total_revenue": 10000.0,
                    "total_cogs": 6000.0,
                    "total_invoices": 25,
                }
            elif "SELECT COALESCE(SUM(amount), 0) FROM expenses" in sql:
                res.scalar.return_value = 1500.0
            elif "FROM invoice_items it" in sql and "top_medicines" in sql.lower() or "GROUP BY m.id" in sql:
                res.mappings.return_value.all.return_value = [
                    {"id": "m-1", "name": "Azithromycin", "dosage_form": "Tablet", "total_quantity": 40, "total_revenue": 3200.0}
                ]
            return res

        conn.execute.side_effect = _execute
        rep = sales_service.reports_summary(engine)
        self.assertEqual(rep["total_revenue"], 10000.0)
        self.assertEqual(rep["total_cogs"], 6000.0)
        self.assertEqual(rep["gross_profit"], 4000.0)
        self.assertEqual(rep["gross_margin_percent"], 40.0)
        self.assertEqual(rep["total_expenses"], 1500.0)
        self.assertEqual(rep["net_profit"], 2500.0)
        self.assertEqual(rep["total_invoices"], 25)
        self.assertEqual(len(rep["top_medicines"]), 1)


if __name__ == "__main__":
    unittest.main()
