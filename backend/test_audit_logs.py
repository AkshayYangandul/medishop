"""
MediShop audit-log tests
========================

Offline tests for the shared audit service, module integrations, login auditing,
read filters/pagination, and admin-only API authorization.  No live database is
used; SQLAlchemy connections are mocked.
"""

import json
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

try:  # Running from backend/ or the repository root.
    import audit_service
    import main as main_mod
    import medicine_service
    import sales_service
    import user_service
    from auth import get_current_user, require_active_admin
except ImportError:  # pragma: no cover - import-path fallback
    from backend import audit_service
    from backend import main as main_mod
    from backend import medicine_service
    from backend import sales_service
    from backend import user_service
    from backend.auth import get_current_user, require_active_admin


def _engine_with(conn):
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    engine.begin.return_value.__exit__.return_value = False
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine


def _audit_inserts(conn):
    rows = []
    for call in conn.execute.call_args_list:
        sql = str(call.args[0]) if call.args else ""
        params = call.args[1] if len(call.args) > 1 else {}
        if "INSERT INTO audit_logs" in sql:
            rows.append((sql, params))
    return rows


class TestAuditSanitisation(unittest.TestCase):
    def test_recursive_secret_redaction(self):
        value = audit_service.sanitize(
            {
                "password_hash": "hash",
                "password": "secret",
                "smtp_password": "smtp",
                "access_token": "token",
                "apiKey": "key",
                "nested": {"app_password": "x", "safe": "visible"},
                "amount": Decimal("12.50"),
            }
        )
        self.assertEqual(value["password_hash"], "[REDACTED]")
        self.assertEqual(value["password"], "[REDACTED]")
        self.assertEqual(value["smtp_password"], "[REDACTED]")
        self.assertEqual(value["access_token"], "[REDACTED]")
        self.assertEqual(value["apiKey"], "[REDACTED]")
        self.assertEqual(value["nested"]["app_password"], "[REDACTED]")
        self.assertEqual(value["nested"]["safe"], "visible")
        self.assertEqual(value["amount"], "12.50")

    def test_pii_masking_helpers(self):
        self.assertEqual(audit_service.mask_email("jane.doe@example.com"), "j***@example.com")
        self.assertEqual(audit_service.mask_email(None), None)
        self.assertEqual(audit_service.mask_phone("9876543210"), "***3210")
        self.assertEqual(audit_service.mask_phone("123"), "***")

    def test_actor_snapshot_uses_live_database_fields(self):
        self.assertEqual(
            audit_service.actor_snapshot(
                {"id": "u1", "full_name": "Alice Admin", "role": "admin"}
            ),
            {"user_id": "u1", "actor_name": "Alice Admin", "actor_role": "admin"},
        )
        self.assertEqual(
            audit_service.actor_snapshot(None, actor_user_id="u2"),
            {"user_id": "u2", "actor_name": None, "actor_role": None},
        )

    def test_record_audit_redacts_and_returns_id(self):
        conn = MagicMock()
        audit_id = audit_service.record_audit(
            conn,
            actor={"id": "u1", "full_name": "Alice", "role": "admin"},
            action="TEST_ACTION",
            module=audit_service.MODULE_SYSTEM,
            entity_type="profiles",
            entity_id="p1",
            description="Test event",
            old_values={"password_hash": "secret", "email": "a@example.com"},
            new_values={"token": "abc", "amount": Decimal("1.20")},
            ip_address="127.0.0.1",
            user_agent="x" * 1000,
        )
        self.assertTrue(audit_id)
        sql, params = conn.execute.call_args.args
        self.assertIn("INSERT INTO audit_logs", str(sql))
        self.assertEqual(params["actor_id"], "u1")
        self.assertEqual(params["actor_name"], "Alice")
        self.assertEqual(params["actor_role"], "admin")
        self.assertEqual(params["action"], "TEST_ACTION")
        self.assertEqual(params["module"], audit_service.MODULE_SYSTEM)
        self.assertEqual(len(params["user_agent"]), 512)
        old = json.loads(params["old_data"])
        new = json.loads(params["new_data"])
        self.assertEqual(old["password_hash"], "[REDACTED]")
        self.assertEqual(old["email"], "a@example.com")
        self.assertEqual(new["token"], "[REDACTED]")
        self.assertEqual(new["amount"], "1.20")


class _ListConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params or {}))
        result = MagicMock()
        if "COUNT(DISTINCT" in sql:
            result.mappings.return_value.first.return_value = {
                "total": 51,
                "today": 3,
                "actors": 2,
                "modules": 4,
            }
        elif "COUNT(*)" in sql:
            result.scalar.return_value = 51
        else:
            result.mappings.return_value.all.return_value = [
                {
                    "id": "a1",
                    "user_id": "u1",
                    "actor_name": "Alice",
                    "actor_role": "admin",
                    "action": "LOGIN_SUCCESS",
                    "module": "auth",
                    "entity_type": "profiles",
                    "entity_id": "u1",
                    "description": "Successful login",
                    "ip_address": "127.0.0.1",
                    "created_at": None,
                }
            ]
        return result


class TestAuditReadService(unittest.TestCase):
    def test_list_applies_filters_and_caps_pagination(self):
        conn = _ListConnection()
        result = audit_service.audit_log_list(
            _engine_with(conn),
            page=0,
            limit=500,
            search="login",
            module="auth",
            action="LOGIN_SUCCESS",
            entity_type="profiles",
            entity_id="u1",
            user_id="u1",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["limit"], 100)
        self.assertEqual(result["total"], 51)
        self.assertEqual(result["total_pages"], 1)
        self.assertEqual(result["stats"]["today"], 3)
        list_sql, list_params = next(
            (sql, params) for sql, params in conn.calls if "LIMIT :limit" in sql
        )
        self.assertIn("a.description LIKE :search", list_sql)
        self.assertIn("a.module = :module", list_sql)
        self.assertIn("a.action = :action", list_sql)
        self.assertIn("a.user_id = :user_id", list_sql)
        self.assertIn("DATE_ADD(:end_date, INTERVAL 1 DAY)", list_sql)
        self.assertEqual(list_params["limit"], 100)
        self.assertEqual(list_params["offset"], 0)
        self.assertEqual(list_params["module"], "auth")

    def test_detail_decodes_old_and_new_json(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "a1",
            "old_data": json.dumps({"role": "pharmacist"}),
            "new_data": json.dumps({"role": "admin", "password_hash": "[REDACTED]"}),
        }
        result = audit_service.audit_log_get(_engine_with(conn), "a1")
        self.assertEqual(result["old_values"], {"role": "pharmacist"})
        self.assertEqual(result["new_values"]["role"], "admin")

    def test_missing_detail_returns_none(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = None
        self.assertIsNone(audit_service.audit_log_get(_engine_with(conn), "missing"))

    def test_options_returns_modules_actions_and_historical_actors(self):
        conn = MagicMock()
        result = MagicMock()

        def _execute(statement, params=None):
            sql = str(statement)
            value = MagicMock()
            if "SELECT DISTINCT module" in sql:
                value.all.return_value = [("auth",), ("inventory",)]
            elif "SELECT DISTINCT action" in sql:
                value.all.return_value = [("LOGIN_SUCCESS",)]
            else:
                value.mappings.return_value.all.return_value = [
                    {"id": "u1", "name": "Deleted User", "role": "admin"}
                ]
            return value

        conn.execute.side_effect = _execute
        options = audit_service.audit_log_options(_engine_with(conn))
        self.assertEqual(options["modules"], ["auth", "inventory"])
        self.assertEqual(options["users"][0]["name"], "Deleted User")


class TestModuleAuditIntegration(unittest.TestCase):
    def test_medicine_create_writes_audit_in_same_connection(self):
        conn = MagicMock()
        conn.execute.return_value.first.return_value = {"id": "cat-1"}
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "med-1",
            "name": "Paracetamol",
            "generic_name": "Paracetamol",
            "category_id": "cat-1",
            "brand_id": None,
            "dosage_form": "Tablet",
            "strength": "500mg",
            "unit": "Strip",
            "hsn_code": "3004",
            "requires_prescription": False,
            "min_stock_alert": 10,
            "is_active": True,
        }
        medicine_service.medicine_create(
            _engine_with(conn),
            {
                "name": "Paracetamol",
                "category_id": "cat-1",
                "dosage_form": "Tablet",
            },
            actor={"id": "admin-1", "full_name": "Admin", "role": "admin"},
        )
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_MEDICINE_CREATED)
        self.assertEqual(params["module"], audit_service.MODULE_INVENTORY)
        self.assertEqual(params["actor_id"], "admin-1")

    def test_invoice_create_writes_summary_audit(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "b-1",
            "medicine_id": "m-1",
            "current_quantity": 20,
            "selling_price": Decimal("10.00"),
            "mrp": Decimal("12.00"),
            "purchase_cost": Decimal("7.00"),
            "medicine_name": "Paracetamol",
        }
        with patch.object(sales_service, "invoice_get", return_value={"id": "inv-1"}):
            result = sales_service.invoice_create(
                _engine_with(conn),
                {
                    "customer_id": None,
                    "payment_method": "cash",
                    "items": [{"medicine_id": "m-1", "batch_id": "b-1", "quantity": 2}],
                },
                created_by="u1",
                actor={"id": "u1", "full_name": "Staff", "role": "pharmacist"},
            )
        self.assertEqual(result["id"], "inv-1")
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_INVOICE_CREATED)
        self.assertEqual(params["module"], audit_service.MODULE_SALES)
        new = json.loads(params["new_data"])
        self.assertEqual(new["item_count"], 1)
        self.assertTrue(new["stock_updated"])

    def test_purchase_create_writes_summary_audit(self):
        conn = MagicMock()

        def _execute(statement, params=None):
            sql = str(statement)
            result = MagicMock()
            if "SELECT id FROM purchases" in sql:
                result.first.return_value = None
            else:
                result.first.return_value = {"id": "exists"}
            result.mappings.return_value.first.return_value = {
                "id": "batch-1",
                "current_quantity": 5,
            }
            return result

        conn.execute.side_effect = _execute
        with patch.object(sales_service, "purchase_get", return_value={"id": "pur-1"}):
            result = sales_service.purchase_create(
                _engine_with(conn),
                {
                    "supplier_id": "s-1",
                    "items": [
                        {
                            "medicine_id": "m-1",
                            "batch_no": "B1",
                            "expiry_date": "2027-05-01",
                            "quantity": 10,
                            "unit_cost": 20,
                            "mrp": 30,
                            "selling_price": 25,
                        }
                    ],
                },
                created_by="u1",
            )
        self.assertEqual(result["id"], "pur-1")
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_PURCHASE_CREATED)
        self.assertEqual(params["module"], audit_service.MODULE_PROCUREMENT)

    def test_expense_create_and_delete_write_audits(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "e-1",
            "title": "Rent",
            "category": "Utilities",
            "amount": Decimal("100.00"),
            "expense_date": "2026-01-01",
            "payment_method": "cash",
        }
        sales_service.expense_create(
            _engine_with(conn),
            {"title": "Rent", "category": "Utilities", "amount": 100},
        )
        self.assertEqual(
            _audit_inserts(conn)[0][1]["action"],
            audit_service.ACTION_EXPENSE_CREATED,
        )

        delete_conn = MagicMock()
        delete_conn.execute.return_value.first.return_value = {
            "id": "e-1",
            "title": "Rent",
            "category": "Utilities",
            "amount": Decimal("100.00"),
            "expense_date": "2026-01-01",
            "payment_method": "cash",
        }
        sales_service.expense_delete(_engine_with(delete_conn), "e-1")
        self.assertEqual(
            _audit_inserts(delete_conn)[0][1]["action"],
            audit_service.ACTION_EXPENSE_DELETED,
        )

    def test_user_create_never_stores_password_hash(self):
        conn = MagicMock()
        conn.execute.return_value.first.return_value = None
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "u-new",
            "email": "new@example.com",
            "full_name": "New Staff",
            "role": "pharmacist",
            "phone": "9876543210",
            "is_active": True,
        }
        with patch.object(user_service, "hash_password", return_value="hashed-value"):
            user_service.user_create(
                _engine_with(conn),
                {
                    "email": "new@example.com",
                    "password": "secret123",
                    "full_name": "New Staff",
                    "role": "pharmacist",
                    "phone": "9876543210",
                },
                created_by="admin-1",
            )
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_USER_CREATED)
        combined = f"{params['old_data']}{params['new_data']}"
        self.assertNotIn("hashed-value", combined)
        self.assertNotIn("secret123", combined)
        self.assertNotIn("new@example.com", combined)
        self.assertNotIn("9876543210", combined)


class TestLoginAudit(unittest.TestCase):
    def _login(self, row, password_valid, update_engine=None):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = row
        engine = update_engine or _engine_with(conn)
        original = main_mod.engine
        main_mod.engine = engine
        try:
            with patch.object(main_mod, "verify_password", return_value=password_valid):
                try:
                    result = main_mod.login(
                        main_mod.LoginRequest(
                            email=(row or {}).get("email", "unknown@example.com"),
                            password="Password123!",
                        )
                    )
                    return result, None
                except HTTPException as exc:
                    return None, exc
        finally:
            main_mod.engine = original

    def _row(self, **overrides):
        row = {
            "id": "u1",
            "email": "alice@example.com",
            "password_hash": "hash",
            "full_name": "Alice",
            "role": "pharmacist",
            "is_active": True,
            "failed_login_attempts": 0,
            "account_locked": False,
            "locked_at": None,
        }
        row.update(overrides)
        return row

    def test_login_success_is_audited(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = self._row()
        engine = _engine_with(conn)
        original = main_mod.engine
        main_mod.engine = engine
        try:
            with patch.object(main_mod, "verify_password", return_value=True):
                main_mod.login(
                    main_mod.LoginRequest(email="alice@example.com", password="Password123!")
                )
        finally:
            main_mod.engine = original
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_LOGIN_SUCCESS)
        self.assertEqual(params["module"], audit_service.MODULE_AUTH)
        self.assertEqual(params["actor_id"], "u1")

    def test_login_failure_is_audited(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = self._row()
        engine = _engine_with(conn)
        original = main_mod.engine
        main_mod.engine = engine
        try:
            with patch.object(main_mod, "verify_password", return_value=False):
                with self.assertRaises(HTTPException) as ctx:
                    main_mod.login(
                        main_mod.LoginRequest(email="alice@example.com", password="wrongpass")
                    )
        finally:
            main_mod.engine = original
        self.assertEqual(ctx.exception.status_code, 401)
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_LOGIN_FAILED)
        self.assertEqual(params["actor_id"], "u1")

    def test_fifth_failure_audits_lock(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = self._row(
            failed_login_attempts=4
        )
        engine = _engine_with(conn)
        original = main_mod.engine
        main_mod.engine = engine
        try:
            with patch.object(main_mod, "verify_password", return_value=False):
                with self.assertRaises(HTTPException):
                    main_mod.login(
                        main_mod.LoginRequest(email="alice@example.com", password="wrongpass")
                    )
        finally:
            main_mod.engine = original
        actions = [params["action"] for _, params in _audit_inserts(conn)]
        self.assertIn(audit_service.ACTION_LOGIN_FAILED, actions)
        self.assertIn(audit_service.ACTION_ACCOUNT_LOCKED, actions)

    def test_unknown_email_failure_is_audited_without_actor(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = None
        engine = _engine_with(conn)
        original = main_mod.engine
        main_mod.engine = engine
        try:
            with patch.object(main_mod, "verify_password", return_value=False):
                with self.assertRaises(HTTPException):
                    main_mod.login(
                        main_mod.LoginRequest(email="unknown@example.com", password="wrongpass")
                    )
        finally:
            main_mod.engine = original
        params = _audit_inserts(conn)[0][1]
        self.assertEqual(params["action"], audit_service.ACTION_LOGIN_FAILED)
        self.assertIsNone(params["actor_id"])
        self.assertNotIn("unknown@example.com", params["description"])


class TestAuditApiSecurity(unittest.TestCase):
    def test_authentication_required(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_pharmacist_is_forbidden(self):
        with self.assertRaises(HTTPException) as ctx:
            require_active_admin({"role": "pharmacist"})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_is_allowed(self):
        admin = {"id": "a1", "role": "admin"}
        self.assertIs(require_active_admin(admin), admin)

    def test_audit_routes_are_read_only(self):
        audit_routes = [
            route
            for route in main_mod.app.routes
            if getattr(route, "path", "").startswith("/api/audit-logs")
        ]
        self.assertGreaterEqual(len(audit_routes), 3)
        self.assertTrue(all("GET" in route.methods for route in audit_routes))


if __name__ == "__main__":
    unittest.main()
