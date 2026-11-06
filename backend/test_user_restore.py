"""Tests for safe restoration of soft-deleted staff accounts."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

try:
    import main as main_mod
    import user_service
    from auth import require_active_admin
except ImportError:  # pragma: no cover
    from backend import main as main_mod
    from backend import user_service
    from backend.auth import require_active_admin


class _Result:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def first(self):
        return self.row


class _RestoreConnection:
    def __init__(self, profile):
        self.profile = profile
        self.calls = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params or {}))
        if sql.startswith("SELECT id, email, full_name, role, deleted_at FROM profiles"):
            return _Result(self.profile)
        if sql.startswith("SELECT id, deleted_at FROM profiles"):
            return _Result(self.profile)
        return _Result()


def _engine_for(conn):
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    engine.begin.return_value.__exit__.return_value = False
    return engine


class TestRestoreUserAccount(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "id": "existing-profile-id",
            "email": "pharmacist@example.test",
            "full_name": "Pharmacist Name",
            "role": "pharmacist",
            "deleted_at": "2026-11-01 12:00:00",
        }

    def test_restore_reuses_profile_and_keeps_it_inactive(self):
        conn = _RestoreConnection(self.profile)
        with patch.object(user_service.audit_service, "record_audit", return_value="audit-1"):
            result = user_service.restore_user_account(
                _engine_for(conn),
                self.profile["email"],
                actor_user_id="admin-1",
                actor={"id": "admin-1", "role": "admin"},
            )

        self.assertEqual(result["id"], self.profile["id"])
        self.assertEqual(result["status"], "restored")
        self.assertFalse(result["is_active"])
        writes = [(sql, params) for sql, params in conn.calls if sql.startswith("UPDATE profiles")]
        self.assertEqual(len(writes), 1)
        self.assertIn("deleted_at = NULL", writes[0][0])
        self.assertIn("is_active = FALSE", writes[0][0])
        self.assertIn("account_locked = FALSE", writes[0][0])
        self.assertIn("failed_login_attempts = 0", writes[0][0])
        self.assertEqual(writes[0][1], {"id": self.profile["id"]})
        self.assertFalse(any(sql.startswith("INSERT INTO profiles") for sql, _ in conn.calls))
        self.assertFalse(any("password_hash" in sql for sql, _ in conn.calls))
        self.assertFalse(any(sql.startswith(("DELETE FROM", "UPDATE purchases", "UPDATE invoices", "UPDATE stock_movements")) for sql, _ in conn.calls))

    def test_restored_inactive_profile_still_cannot_authenticate(self):
        try:
            from auth import _load_profile_from_db
        except ImportError:  # pragma: no cover
            from backend.auth import _load_profile_from_db
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": self.profile["id"],
            "email": self.profile["email"],
            "role": "pharmacist",
            "is_active": False,
        }
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        with self.assertRaises(HTTPException) as ctx:
            _load_profile_from_db(self.profile["id"], engine)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_active_duplicate_is_not_restored(self):
        active = {**self.profile, "deleted_at": None}
        conn = _RestoreConnection(active)
        with self.assertRaises(HTTPException) as ctx:
            user_service.restore_user_account(_engine_for(conn), active["email"], actor_user_id="admin-1")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertFalse(any(sql.startswith("UPDATE profiles") for sql, _ in conn.calls))

    def test_missing_profile_is_not_created_by_restore(self):
        conn = _RestoreConnection(None)
        with self.assertRaises(HTTPException) as ctx:
            user_service.restore_user_account(_engine_for(conn), "missing@example.test", actor_user_id="admin-1")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertFalse(any(sql.startswith("INSERT INTO profiles") for sql, _ in conn.calls))

    def test_create_reports_soft_deleted_duplicate_separately(self):
        conn = _RestoreConnection(self.profile)
        with patch.object(user_service, "hash_password", return_value="hashed"):
            with self.assertRaises(HTTPException) as ctx:
                user_service.user_create(
                    _engine_for(conn),
                    {"email": self.profile["email"], "password": "password123", "full_name": "Other Name"},
                )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Confirm restoration", ctx.exception.detail)
        self.assertFalse(any(sql.startswith("INSERT INTO profiles") for sql, _ in conn.calls))

    def test_create_still_rejects_an_active_duplicate(self):
        active = {**self.profile, "deleted_at": None}
        conn = _RestoreConnection(active)
        with patch.object(user_service, "hash_password", return_value="hashed"):
            with self.assertRaises(HTTPException) as ctx:
                user_service.user_create(
                    _engine_for(conn),
                    {"email": active["email"], "password": "password123", "full_name": "Other Name"},
                )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "A user with this email address already exists.")
        self.assertFalse(any(sql.startswith("INSERT INTO profiles") for sql, _ in conn.calls))

    def test_restore_route_requires_active_admin(self):
        route = next(
            r for r in main_mod.app.routes
            if getattr(r, "path", None) == "/api/users/restore"
            and "POST" in getattr(r, "methods", set())
        )
        dependencies = [dep.call for dep in route.dependant.dependencies]
        self.assertIn(require_active_admin, dependencies)
        with self.assertRaises(HTTPException) as ctx:
            require_active_admin(current_user={"id": "p-1", "role": "pharmacist", "is_active": True})
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
