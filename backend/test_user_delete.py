"""
MediShop account-deletion tests
================================

Covers the administrator-only ``DELETE /api/users/{user_id}`` behaviour:

* successful deletion of an eligible account;
* authorization (active admin only, authenticated only);
* self-deletion protection;
* last-active-administrator protection;
* 404 for a missing account;
* soft-deletion preserves historical business records and actor identity;
* audit history is immutable and receives a deletion event;
* rollback when the audit insert fails;
* deleted accounts can no longer authenticate.

These are **offline unit tests**: SQL calls are served by a small fake
connection that inspects the statement text, and no live database or SMTP
server is used.
"""

import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

try:  # Running from backend/ or the repository root.
    import main as main_mod
    from user_service import delete_user_account, user_list
    from auth import require_active_admin, get_current_user, _load_profile_from_db
except ImportError:  # pragma: no cover - import-path fallback
    from backend import main as main_mod
    from backend.user_service import delete_user_account, user_list
    from backend.auth import require_active_admin, get_current_user, _load_profile_from_db


# ---------------------------------------------------------------------------
# Fake SQLAlchemy connection
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, *, scalar_value=None, first_row=None, all_rows=None):
        self._scalar = scalar_value
        self._first = first_row
        if all_rows is not None:
            self._all = all_rows
        elif first_row is not None:
            self._all = [first_row]
        else:
            self._all = []

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all


class _FakeTransaction:
    def __init__(self):
        self.is_active = True
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True
        self.is_active = False

    def rollback(self):
        self.rolled_back = True
        self.is_active = False


class _FakeConnection:
    """Routes ``execute`` by statement text and records every statement."""

    def __init__(
        self,
        target,
        active_admins=None,
        reference_count=0,
        fail_on_audit=False,
    ):
        self.target = target
        self.active_admins = active_admins if active_admins is not None else []
        self.reference_count = reference_count
        self.fail_on_audit = fail_on_audit
        self.executed = []
        self.transaction = _FakeTransaction()
        self.released = False
        self.commits = 0

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        upper = sql.upper()
        params = params or {}
        self.executed.append((sql, params))

        if upper.startswith("SELECT GET_LOCK"):
            return _FakeResult(scalar_value=1)
        if upper.startswith("SELECT RELEASE_LOCK"):
            self.released = True
            return _FakeResult(scalar_value=1)
        if upper.startswith(
            "SELECT ID, EMAIL, FULL_NAME, ROLE, IS_ACTIVE FROM PROFILES"
        ):
            return _FakeResult(first_row=self.target)
        if upper.startswith("SELECT ID FROM PROFILES WHERE ROLE = 'ADMIN'"):
            return _FakeResult(all_rows=self.active_admins)
        if upper.startswith("DELETE FROM PASSWORD_RESETS"):
            return _FakeResult(scalar_value=0)
        if upper.startswith("UPDATE PROFILES SET DELETED_AT"):
            return _FakeResult(scalar_value=1)
        if upper.startswith("INSERT INTO AUDIT_LOGS"):
            if self.fail_on_audit:
                raise RuntimeError("simulated audit insert failure")
            return _FakeResult(scalar_value=1)

        raise AssertionError(f"Unexpected SQL in delete test: {sql}")

    def begin(self):
        return self.transaction

    def commit(self):
        self.commits += 1

    def invalidate(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _engine_with(conn):
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine


# ---------------------------------------------------------------------------
# Statement helpers
# ---------------------------------------------------------------------------

def _executed(conn):
    return conn.executed


def _profile_deletes(conn):
    return [
        (sql, params)
        for sql, params in _executed(conn)
        if sql.upper().startswith("DELETE FROM PROFILES")
    ]


def _profile_soft_deletes(conn):
    return [
        (sql, params)
        for sql, params in _executed(conn)
        if sql.upper().startswith("UPDATE PROFILES SET DELETED_AT")
    ]


def _password_reset_deletes(conn):
    return [
        (sql, params)
        for sql, params in _executed(conn)
        if sql.upper().startswith("DELETE FROM PASSWORD_RESETS")
    ]


def _audit_inserts(conn):
    return [
        (sql, params)
        for sql, params in _executed(conn)
        if sql.upper().startswith("INSERT INTO AUDIT_LOGS")
    ]


def _historical_writes(conn):
    """Any DELETE/UPDATE aimed at a historical business/audit table."""
    tables = (
        "PURCHASES",
        "INVOICES",
        "STOCK_MOVEMENTS",
        "EXPENSES",
        "AUDIT_LOGS",
    )
    writes = []
    for sql, params in _executed(conn):
        upper = sql.upper()
        for table in tables:
            if upper.startswith(f"DELETE FROM {table}") or upper.startswith(
                f"UPDATE {table}"
            ):
                writes.append((sql, params))
    return writes


def _pharmacist_profile(**overrides):
    profile = {
        "id": "target-1",
        "email": "pharmacist@medishop.local",
        "full_name": "Jane Pharmacist",
        "role": "pharmacist",
        "is_active": True,
    }
    profile.update(overrides)
    return profile


def _admin_profile(**overrides):
    profile = {
        "id": "admin-2",
        "email": "second.admin@medishop.local",
        "full_name": "Second Admin",
        "role": "admin",
        "is_active": True,
    }
    profile.update(overrides)
    return profile


class TestDeleteUserAccountAuthorization(unittest.TestCase):
    """Route-level authorization dependencies (no DB)."""

    def test_non_admin_user_is_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            require_active_admin(
                current_user={"id": "u", "role": "pharmacist", "is_active": True}
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_unauthenticated_request_is_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(credentials=None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_active_admin_passes_dependency(self):
        result = require_active_admin(
            current_user={"id": "u", "role": "admin", "is_active": True}
        )
        self.assertEqual(result["id"], "u")

    def test_delete_route_is_registered(self):
        matches = [
            route
            for route in main_mod.app.routes
            if getattr(route, "path", None) == "/api/users/{user_id}"
            and "DELETE" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(matches), 1)


class TestPanelAccountLockState(unittest.TestCase):
    def test_user_list_includes_lock_state_but_not_credentials(self):
        row = {
            "id": "p-1",
            "full_name": "Locked Pharmacist",
            "email": "locked@example.test",
            "role": "pharmacist",
            "phone": None,
            "is_active": 1,
            "failed_login_attempts": 5,
            "account_locked": 1,
            "locked_at": "2026-11-06 10:00:00",
        }
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.all.return_value = [row]
        engine = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        engine.begin.return_value.__exit__.return_value = False

        result = user_list(engine)

        self.assertIs(result[0]["account_locked"], True)
        self.assertIs(result[0]["is_active"], True)
        self.assertEqual(result[0]["failed_login_attempts"], 5)
        self.assertEqual(result[0]["locked_at"], row["locked_at"])
        self.assertNotIn("password_hash", result[0])
        self.assertIn("WHERE deleted_at IS NULL", str(conn.execute.call_args.args[0]))


class TestDeleteUserAccountService(unittest.TestCase):
    """Service-level deletion safeguards and transaction behaviour."""

    def test_admin_successfully_deletes_eligible_account(self):
        conn = _FakeConnection(
            target=_pharmacist_profile(),
            reference_count=0,
        )

        result = delete_user_account(
            _engine_with(conn), "target-1", actor_user_id="admin-1"
        )

        self.assertEqual(result["id"], "target-1")
        self.assertEqual(result["email"], "pharmacist@medishop.local")
        self.assertEqual(result["status"], "deleted")
        self.assertTrue(result["audit_id"])
        self.assertTrue(conn.transaction.committed)
        self.assertFalse(conn.transaction.rolled_back)

        self.assertEqual(_profile_deletes(conn), [])
        self.assertEqual(len(_profile_soft_deletes(conn)), 1)
        self.assertIn("IS_ACTIVE = FALSE", _profile_soft_deletes(conn)[0][0].upper())
        self.assertIn("ACCOUNT_LOCKED = TRUE", _profile_soft_deletes(conn)[0][0].upper())
        self.assertEqual(_profile_soft_deletes(conn)[0][1], {"id": "target-1"})
        self.assertEqual(len(_password_reset_deletes(conn)), 1)

        audits = _audit_inserts(conn)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0][1]["actor_id"], "admin-1")
        self.assertEqual(audits[0][1]["action"], "ACCOUNT_DELETE")

        # No historical/business table is ever deleted or updated.
        self.assertEqual(_historical_writes(conn), [])
        self.assertTrue(conn.released, "the admin mutex must be released")

    def test_admin_cannot_delete_own_account(self):
        conn = _FakeConnection(
            target=_admin_profile(id="admin-1"),
            active_admins=[{"id": "admin-1"}],
            reference_count=0,
        )

        with self.assertRaises(HTTPException) as ctx:
            delete_user_account(
                _engine_with(conn), "admin-1", actor_user_id="admin-1"
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("own account", ctx.exception.detail.lower())
        self.assertTrue(conn.transaction.rolled_back)
        self.assertFalse(conn.transaction.committed)
        self.assertEqual(_profile_deletes(conn), [])
        self.assertTrue(conn.released)

    def test_last_active_admin_is_protected(self):
        conn = _FakeConnection(
            target=_admin_profile(),
            active_admins=[{"id": "admin-2"}],
            reference_count=0,
        )

        with self.assertRaises(HTTPException) as ctx:
            delete_user_account(
                _engine_with(conn), "admin-2", actor_user_id="admin-1"
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("last active administrator", ctx.exception.detail.lower())
        self.assertTrue(conn.transaction.rolled_back)
        self.assertEqual(_profile_deletes(conn), [])

    def test_deleting_one_of_two_active_admins_is_allowed(self):
        conn = _FakeConnection(
            target=_admin_profile(),
            active_admins=[{"id": "admin-1"}, {"id": "admin-2"}],
            reference_count=0,
        )

        result = delete_user_account(
            _engine_with(conn), "admin-2", actor_user_id="admin-1"
        )

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(_profile_deletes(conn), [])
        self.assertEqual(len(_profile_soft_deletes(conn)), 1)

    def test_nonexistent_account_returns_404(self):
        conn = _FakeConnection(target=None, reference_count=0)

        with self.assertRaises(HTTPException) as ctx:
            delete_user_account(
                _engine_with(conn), "missing-id", actor_user_id="admin-1"
            )

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertTrue(conn.transaction.rolled_back)
        self.assertEqual(_profile_deletes(conn), [])

    def test_empty_target_id_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            delete_user_account(MagicMock(), "", actor_user_id="admin-1")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_historical_records_are_preserved_by_soft_deletion(self):
        conn = _FakeConnection(
            target=_pharmacist_profile(),
            reference_count=2,
        )

        result = delete_user_account(
            _engine_with(conn), "target-1", actor_user_id="admin-1"
        )

        self.assertEqual(result["status"], "deleted")
        self.assertTrue(conn.transaction.committed)
        # Profile identity remains; no historical table is deleted or updated.
        self.assertEqual(_profile_deletes(conn), [])
        self.assertEqual(len(_profile_soft_deletes(conn)), 1)
        self.assertEqual(len(_password_reset_deletes(conn)), 1)
        self.assertEqual(_historical_writes(conn), [])

    def test_deleted_profile_is_not_returned_for_authenticated_requests(self):
        conn = MagicMock()
        conn.execute.return_value.mappings.return_value.first.return_value = None
        engine = _engine_with(conn)

        with self.assertRaises(HTTPException) as ctx:
            _load_profile_from_db("target-1", engine)

        self.assertEqual(ctx.exception.status_code, 401)
        sql = str(conn.execute.call_args.args[0])
        self.assertIn("deleted_at IS NULL", sql)

    def test_audit_failure_rolls_back_deletion(self):
        conn = _FakeConnection(
            target=_pharmacist_profile(),
            reference_count=0,
            fail_on_audit=True,
        )

        with self.assertRaises(HTTPException) as ctx:
            delete_user_account(
                _engine_with(conn), "target-1", actor_user_id="admin-1"
            )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertTrue(conn.transaction.rolled_back)
        self.assertFalse(conn.transaction.committed)
        self.assertTrue(conn.released)

    def test_deleted_account_cannot_authenticate(self):
        # 1. Delete the account.
        delete_conn = _FakeConnection(
            target=_pharmacist_profile(),
            reference_count=0,
        )
        delete_user_account(
            _engine_with(delete_conn), "target-1", actor_user_id="admin-1"
        )
        self.assertEqual(_profile_deletes(delete_conn), [])
        self.assertEqual(len(_profile_soft_deletes(delete_conn)), 1)

        # 2. A subsequent login for the same email finds no profile row and is
        #    rejected with the generic 401 (no token issued).
        login_conn = MagicMock()
        login_conn.execute.return_value.mappings.return_value.first.return_value = None
        login_engine = MagicMock()
        login_engine.connect.return_value.__enter__.return_value = login_conn
        login_engine.connect.return_value.__exit__.return_value = False

        real_engine = main_mod.engine
        main_mod.engine = login_engine
        try:
            with self.assertRaises(HTTPException) as ctx:
                main_mod.login(
                    main_mod.LoginRequest(
                        email="pharmacist@medishop.local",
                        password="any-password",
                    )
                )
        finally:
            main_mod.engine = real_engine

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password.")
        login_queries = [
            " ".join(str(call.args[0]).split())
            for call in login_conn.execute.call_args_list
            if "FROM profiles" in str(call.args[0])
        ]
        self.assertTrue(login_queries)
        self.assertIn("deleted_at IS NULL", login_queries[0])


if __name__ == "__main__":
    unittest.main()
