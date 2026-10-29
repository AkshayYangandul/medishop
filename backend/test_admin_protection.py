"""
MediShop admin-protection test suite
======================================
All classes in ``TestAuth*`` and ``TestUserService*`` are **offline unit tests**:
they never open a real database connection.  All SQL calls are replaced by
``unittest.mock.MagicMock`` objects.

The ``TestLiveMySQL`` class contains **integration tests** that require a real,
disposable MySQL database.  They are unconditionally skipped unless the environment
variable ``RUN_LIVE_MYSQL_TESTS=1`` is set AND ``TEST_DATABASE_URL`` is provided.
Do **not** set ``RUN_LIVE_MYSQL_TESTS=1`` against the production ``medishop`` database.
"""

import os
import json
import time
import unittest
from unittest.mock import MagicMock, patch, call

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers to import modules from either the package or direct path
# ---------------------------------------------------------------------------
def _import_user_service():
    try:
        from user_service import (
            update_user_role_or_status,
            provision_initial_admin,
            ADMIN_ROLE_MUTEX_NAME,
            InitialAdminOutcome,
        )
    except ImportError:
        from backend.user_service import (
            update_user_role_or_status,
            provision_initial_admin,
            ADMIN_ROLE_MUTEX_NAME,
            InitialAdminOutcome,
        )
    return update_user_role_or_status, provision_initial_admin, ADMIN_ROLE_MUTEX_NAME, InitialAdminOutcome


def _import_auth():
    try:
        import auth as auth_mod
    except ImportError:
        import backend.auth as auth_mod
    return auth_mod


(
    update_user_role_or_status,
    provision_initial_admin,
    ADMIN_ROLE_MUTEX_NAME,
    InitialAdminOutcome,
) = _import_user_service()
auth_mod = _import_auth()


# ---------------------------------------------------------------------------
# Shared mock-connection builder
# ---------------------------------------------------------------------------

def _make_engine_with_conn(conn):
    """Returns a mock engine whose context-manager yields ``conn``."""
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine


def _make_conn_with_lock(lock_return=1):
    """
    Returns a mock connection whose first execute() returns ``lock_return``
    for GET_LOCK and a MagicMock for any other statement.
    Subsequent calls fall through to MagicMock default behaviour.
    """
    conn = MagicMock()
    executed = []

    def _execute(stmt, params=None):
        sql = str(stmt)
        executed.append((sql, params))
        result = MagicMock()
        if "GET_LOCK" in sql:
            result.scalar.return_value = lock_return
        return result

    conn.execute.side_effect = _execute
    conn._executed = executed  # expose for assertions
    return conn


# ===========================================================================
# AUTH MODULE TESTS
# ===========================================================================

class TestAuthSecretKeyValidation(unittest.TestCase):
    """
    Verify that the module raises RuntimeError at import time when AUTH_SECRET_KEY
    is absent or too short.
    """

    def _reimport_auth(self, env: dict):
        """Reimport the auth module under a patched environment."""
        import importlib
        import sys
        # Remove cached module so reimport triggers module-level code
        for key in list(sys.modules.keys()):
            if "auth" in key and "test" not in key:
                del sys.modules[key]
        with patch.dict(os.environ, env, clear=True):
            # Stub database import so we don't need a real DB
            sys.modules.setdefault("database", MagicMock())
            sys.modules.setdefault("backend.database", MagicMock())
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "auth_under_test",
                    os.path.join(os.path.dirname(__file__), "auth.py"),
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
            except RuntimeError as exc:
                raise

    def test_missing_secret_key_raises(self):
        """Application must refuse to start when AUTH_SECRET_KEY is not set."""
        with self.assertRaises(RuntimeError) as ctx:
            self._reimport_auth({"AUTH_SECRET_KEY": ""})
        self.assertIn("AUTH_SECRET_KEY", str(ctx.exception))

    def test_short_secret_key_raises(self):
        """Application must refuse to start when AUTH_SECRET_KEY is shorter than 32 chars."""
        with self.assertRaises(RuntimeError) as ctx:
            self._reimport_auth({"AUTH_SECRET_KEY": "tooshort"})
        self.assertIn("too short", str(ctx.exception))

    def test_sufficient_secret_key_succeeds(self):
        """A 32-character key must load without raising."""
        mod = self._reimport_auth({"AUTH_SECRET_KEY": "a" * 32})
        self.assertIsNotNone(mod)


class TestDecodeAccessToken(unittest.TestCase):
    """Tests for decode_access_token — no DB connection required."""

    def setUp(self):
        self._key = "a" * 32
        self._token = auth_mod.create_access_token("uid-1", "a@b.com", "admin", secret_key=self._key)

    def test_valid_token_decodes(self):
        payload = auth_mod.decode_access_token(self._token, secret_key=self._key)
        self.assertEqual(payload["sub"], "uid-1")
        self.assertEqual(payload["role"], "admin")
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)

    def test_tampered_signature_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token(self._token + "x", secret_key=self._key)
        self.assertIn("signature", str(ctx.exception))

    def test_wrong_key_rejected(self):
        with self.assertRaises(ValueError):
            auth_mod.decode_access_token(self._token, secret_key="b" * 32)

    def test_expired_token_rejected(self):
        tok = auth_mod.create_access_token("uid-1", "a@b.com", "admin", expires_in=-10, secret_key=self._key)
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token(tok, secret_key=self._key)
        self.assertIn("expired", str(ctx.exception))

    def test_missing_exp_claim_rejected(self):
        """Manually craft a token without 'exp'."""
        import json, base64, hmac, hashlib
        def b64(d): return base64.urlsafe_b64encode(d).decode().rstrip("=")
        header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(json.dumps({"sub": "uid-1", "iat": int(time.time())}).encode())
        sig_input = f"{header}.{payload}".encode()
        sig = b64(hmac.new(self._key.encode(), sig_input, hashlib.sha256).digest())
        tok = f"{header}.{payload}.{sig}"
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token(tok, secret_key=self._key)
        self.assertIn("exp", str(ctx.exception))

    def test_missing_sub_claim_rejected(self):
        """Manually craft a token without 'sub'."""
        import json, base64, hmac, hashlib
        def b64(d): return base64.urlsafe_b64encode(d).decode().rstrip("=")
        now = int(time.time())
        header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(json.dumps({"exp": now + 3600, "iat": now}).encode())
        sig_input = f"{header}.{payload}".encode()
        sig = b64(hmac.new(self._key.encode(), sig_input, hashlib.sha256).digest())
        tok = f"{header}.{payload}.{sig}"
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token(tok, secret_key=self._key)
        self.assertIn("sub", str(ctx.exception))

    def test_wrong_algorithm_rejected(self):
        """Manually craft a token with alg=none."""
        import json, base64, hmac, hashlib
        def b64(d): return base64.urlsafe_b64encode(d).decode().rstrip("=")
        now = int(time.time())
        header = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        payload = b64(json.dumps({"sub": "uid-1", "exp": now + 3600, "iat": now}).encode())
        sig_input = f"{header}.{payload}".encode()
        sig = b64(hmac.new(self._key.encode(), sig_input, hashlib.sha256).digest())
        tok = f"{header}.{payload}.{sig}"
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token(tok, secret_key=self._key)
        self.assertIn("HS256", str(ctx.exception))

    def test_malformed_token_no_dots_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token("notavalidtoken", secret_key=self._key)
        self.assertIn("three dot-separated", str(ctx.exception))

    def test_malformed_token_two_parts_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token("header.payload", secret_key=self._key)
        self.assertIn("three dot-separated", str(ctx.exception))

    def test_iat_far_future_rejected(self):
        """A token with iat > now + 60 s should be rejected."""
        import json, base64, hmac, hashlib
        def b64(d): return base64.urlsafe_b64encode(d).decode().rstrip("=")
        now = int(time.time())
        header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(json.dumps({"sub": "uid-1", "exp": now + 7200, "iat": now + 9999}).encode())
        sig_input = f"{header}.{payload}".encode()
        sig = b64(hmac.new(self._key.encode(), sig_input, hashlib.sha256).digest())
        tok = f"{header}.{payload}.{sig}"
        with self.assertRaises(ValueError) as ctx:
            auth_mod.decode_access_token(tok, secret_key=self._key)
        self.assertIn("iat", str(ctx.exception))


class TestPasswordHashing(unittest.TestCase):
    """Tests for hash_password and verify_password."""

    def test_correct_password_verifies(self):
        h = auth_mod.hash_password("correct-horse-battery-staple")
        self.assertTrue(auth_mod.verify_password("correct-horse-battery-staple", h))

    def test_wrong_password_rejected(self):
        h = auth_mod.hash_password("correct-horse-battery-staple")
        self.assertFalse(auth_mod.verify_password("wrongpassword", h))

    def test_empty_password_does_not_raise(self):
        # verify_password must return False, not raise, for malformed inputs
        self.assertFalse(auth_mod.verify_password("pass", ""))

    def test_malformed_hash_returns_false(self):
        self.assertFalse(auth_mod.verify_password("pass", "not-a-valid-hash"))
        self.assertFalse(auth_mod.verify_password("pass", "pbkdf2_sha256$abc$def"))
        self.assertFalse(auth_mod.verify_password("pass", "unknown_scheme$260000$salt$hex"))

    def test_different_hashes_for_same_password(self):
        h1 = auth_mod.hash_password("same")
        h2 = auth_mod.hash_password("same")
        self.assertNotEqual(h1, h2, "Two hashes of the same password must differ (random salt)")
        self.assertTrue(auth_mod.verify_password("same", h1))
        self.assertTrue(auth_mod.verify_password("same", h2))

    def test_hash_format_is_self_describing(self):
        h = auth_mod.hash_password("test123")
        parts = h.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "pbkdf2_sha256")
        self.assertTrue(parts[1].isdigit())


class TestGetCurrentUserDependency(unittest.TestCase):
    """Tests for get_current_user() FastAPI dependency — no real DB."""

    def _make_credentials(self, token: str):
        creds = MagicMock()
        creds.credentials = token
        return creds

    def test_missing_credentials_returns_401(self):
        with self.assertRaises(HTTPException) as ctx:
            auth_mod.get_current_user(credentials=None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_bearer_returns_401(self):
        creds = MagicMock()
        creds.credentials = ""
        with self.assertRaises(HTTPException) as ctx:
            auth_mod.get_current_user(credentials=creds)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_invalid_token_returns_401(self):
        creds = self._make_credentials("not.a.valid.jwt.token.with.extra.dots")
        with self.assertRaises(HTTPException) as ctx:
            auth_mod.get_current_user(credentials=creds)
        self.assertEqual(ctx.exception.status_code, 401)
        # Must not leak the specific reason (expired vs bad sig)
        self.assertNotIn("signature", ctx.exception.detail)
        self.assertNotIn("expired", ctx.exception.detail)

    def test_valid_token_for_inactive_user_returns_403(self):
        tok = auth_mod.create_access_token("uid-1", "a@b.com", "admin")
        creds = self._make_credentials(tok)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "uid-1", "email": "a@b.com", "role": "admin", "is_active": 0
        }

        with patch.object(auth_mod.default_engine, "connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_connect.return_value.__exit__.return_value = False
            with self.assertRaises(HTTPException) as ctx:
                auth_mod.get_current_user(credentials=creds)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_valid_token_for_missing_profile_returns_401(self):
        tok = auth_mod.create_access_token("uid-missing", "a@b.com", "admin")
        creds = self._make_credentials(tok)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.mappings.return_value.first.return_value = None

        with patch.object(auth_mod.default_engine, "connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_connect.return_value.__exit__.return_value = False
            with self.assertRaises(HTTPException) as ctx:
                auth_mod.get_current_user(credentials=creds)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_valid_token_for_active_admin_returns_profile(self):
        tok = auth_mod.create_access_token("uid-1", "a@b.com", "admin")
        creds = self._make_credentials(tok)

        mock_conn = MagicMock()
        mock_conn.execute.return_value.mappings.return_value.first.return_value = {
            "id": "uid-1", "email": "a@b.com", "role": "admin", "is_active": 1
        }

        with patch.object(auth_mod.default_engine, "connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value = mock_conn
            mock_connect.return_value.__exit__.return_value = False
            result = auth_mod.get_current_user(credentials=creds)
        self.assertEqual(result["id"], "uid-1")
        self.assertEqual(result["role"], "admin")


class TestRequireActiveAdminDependency(unittest.TestCase):
    """Tests for require_active_admin() — no DB."""

    def test_pharmacist_gets_403(self):
        with self.assertRaises(HTTPException) as ctx:
            auth_mod.require_active_admin(current_user={"id": "u", "role": "pharmacist", "is_active": 1})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_admin_passes_through(self):
        result = auth_mod.require_active_admin(
            current_user={"id": "u", "role": "admin", "is_active": 1}
        )
        self.assertEqual(result["id"], "u")


# ===========================================================================
# USER SERVICE TESTS
# ===========================================================================

class TestUpdateUserRoleOrStatus(unittest.TestCase):
    """Offline unit tests for update_user_role_or_status()."""

    # -----------------------------------------------------------------------
    # Input validation (no DB connection opened)
    # -----------------------------------------------------------------------

    def test_empty_update_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(MagicMock(), "uid", new_role=None, new_is_active=None)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No update fields", ctx.exception.detail)

    def test_invalid_role_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(MagicMock(), "uid", new_role="superadmin")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("superadmin", ctx.exception.detail)

    # -----------------------------------------------------------------------
    # Lock acquisition failures
    # -----------------------------------------------------------------------

    def _engine_lock(self, lock_return):
        """Build a mock engine/conn that returns lock_return from GET_LOCK."""
        conn = MagicMock()
        result = MagicMock()
        result.scalar.return_value = lock_return
        conn.execute.return_value = result
        return _make_engine_with_conn(conn), conn

    def test_lock_timeout_returns_503(self):
        engine, _ = self._engine_lock(0)
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(engine, "uid", new_role="pharmacist")
        self.assertEqual(ctx.exception.status_code, 503)

    def test_lock_null_returns_500(self):
        engine, _ = self._engine_lock(None)
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(engine, "uid", new_role="pharmacist")
        self.assertEqual(ctx.exception.status_code, 500)

    # -----------------------------------------------------------------------
    # Last-admin protection
    # -----------------------------------------------------------------------

    def _build_engine_for_scenario(self, active_admins, target_profile):
        """
        Returns a mock engine whose conn simulates:
        - GET_LOCK returns 1
        - Active admin row query returns ``active_admins`` (list of dicts)
        - Target profile query returns ``target_profile`` (dict or None)
        """
        conn = MagicMock()
        conn.begin.return_value.is_active = True
        executed = []

        def _execute(stmt, params=None):
            sql = str(stmt)
            executed.append((sql, params))
            result = MagicMock()
            if "GET_LOCK" in sql:
                result.scalar.return_value = 1
            elif "WHERE role = 'admin' AND is_active = TRUE FOR UPDATE" in sql:
                result.mappings.return_value.all.return_value = active_admins
            elif "WHERE id = :id FOR UPDATE" in sql:
                result.mappings.return_value.first.return_value = target_profile
            return result

        conn.execute.side_effect = _execute
        conn._executed = executed
        return _make_engine_with_conn(conn), conn

    def test_sole_admin_demotion_rejected(self):
        engine, conn = self._build_engine_for_scenario(
            active_admins=[{"id": "a1", "role": "admin", "is_active": 1}],
            target_profile={"id": "a1", "role": "admin", "is_active": 1},
        )
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(engine, "a1", new_role="pharmacist")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("last active administrator", ctx.exception.detail)

        # RELEASE_LOCK must always be called in finally
        release_calls = [s for s, _ in conn._executed if "RELEASE_LOCK" in s]
        self.assertGreaterEqual(len(release_calls), 1, "RELEASE_LOCK must be called in finally")

    def test_sole_admin_deactivation_rejected(self):
        engine, conn = self._build_engine_for_scenario(
            active_admins=[{"id": "a1", "role": "admin", "is_active": 1}],
            target_profile={"id": "a1", "role": "admin", "is_active": 1},
        )
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(engine, "a1", new_is_active=False)
        self.assertEqual(ctx.exception.status_code, 403)

        release_calls = [s for s, _ in conn._executed if "RELEASE_LOCK" in s]
        self.assertGreaterEqual(len(release_calls), 1)

    def test_demotion_allowed_with_two_admins(self):
        engine, conn = self._build_engine_for_scenario(
            active_admins=[
                {"id": "a1", "role": "admin", "is_active": 1},
                {"id": "a2", "role": "admin", "is_active": 1},
            ],
            target_profile={"id": "a1", "role": "admin", "is_active": 1},
        )
        result = update_user_role_or_status(engine, "a1", new_role="pharmacist", actor_user_id="a2")
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["role"], "pharmacist")
        self.assertIn("audit_id", result)

    def test_target_not_found_returns_404(self):
        engine, conn = self._build_engine_for_scenario(
            active_admins=[{"id": "a1", "role": "admin", "is_active": 1}],
            target_profile=None,
        )
        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(engine, "nonexistent", new_role="pharmacist")
        self.assertEqual(ctx.exception.status_code, 404)

    # -----------------------------------------------------------------------
    # Audit content safety
    # -----------------------------------------------------------------------

    def test_audit_excludes_password_hash(self):
        engine, conn = self._build_engine_for_scenario(
            active_admins=[
                {"id": "a1", "role": "admin", "is_active": 1},
                {"id": "a2", "role": "admin", "is_active": 1},
            ],
            target_profile={"id": "a1", "role": "admin", "is_active": 1},
        )
        update_user_role_or_status(engine, "a1", new_role="pharmacist", actor_user_id="a2")

        audit_calls = [(s, p) for s, p in conn._executed if "INSERT INTO audit_logs" in s]
        self.assertEqual(len(audit_calls), 1)
        params = audit_calls[0][1]
        old_data = json.loads(params["old_data"])
        new_data = json.loads(params["new_data"])
        self.assertNotIn("password_hash", old_data)
        self.assertNotIn("password_hash", new_data)
        self.assertNotIn("email", old_data)

    # -----------------------------------------------------------------------
    # Audit insertion failure → profile update rolls back
    # -----------------------------------------------------------------------

    def test_audit_insert_failure_rolls_back_profile_update(self):
        """If the audit INSERT raises, the transaction must be rolled back."""
        conn = MagicMock()
        trans = MagicMock()
        trans.is_active = True
        conn.begin.return_value = trans
        executed = []

        def _execute(stmt, params=None):
            sql = str(stmt)
            executed.append(sql)
            result = MagicMock()
            if "GET_LOCK" in sql:
                result.scalar.return_value = 1
            elif "WHERE role = 'admin' AND is_active = TRUE FOR UPDATE" in sql:
                result.mappings.return_value.all.return_value = [
                    {"id": "a1", "role": "admin", "is_active": 1},
                    {"id": "a2", "role": "admin", "is_active": 1},
                ]
            elif "WHERE id = :id FOR UPDATE" in sql:
                result.mappings.return_value.first.return_value = {
                    "id": "a1", "role": "admin", "is_active": 1
                }
            elif "INSERT INTO audit_logs" in sql:
                raise RuntimeError("Simulated audit_logs write failure")
            return result

        conn.execute.side_effect = _execute
        conn._executed = executed
        engine = _make_engine_with_conn(conn)

        with self.assertRaises(HTTPException) as ctx:
            update_user_role_or_status(engine, "a1", new_role="pharmacist", actor_user_id="a2")
        self.assertEqual(ctx.exception.status_code, 500)

        # The transaction must have been rolled back
        trans.rollback.assert_called_once()
        # RELEASE_LOCK still runs
        release_calls = [s for s in executed if "RELEASE_LOCK" in s]
        self.assertGreaterEqual(len(release_calls), 1)

    # -----------------------------------------------------------------------
    # Lock release failure → connection invalidated
    # -----------------------------------------------------------------------

    def test_lock_release_failure_invalidates_connection(self):
        """When RELEASE_LOCK raises, conn.invalidate() must be called."""
        conn = MagicMock()
        trans = MagicMock()
        trans.is_active = True
        conn.begin.return_value = trans
        executed = []
        release_call_count = [0]

        def _execute(stmt, params=None):
            sql = str(stmt)
            executed.append(sql)
            result = MagicMock()
            if "GET_LOCK" in sql:
                result.scalar.return_value = 1
            elif "WHERE role = 'admin' AND is_active = TRUE FOR UPDATE" in sql:
                result.mappings.return_value.all.return_value = [
                    {"id": "a1", "role": "admin", "is_active": 1},
                    {"id": "a2", "role": "admin", "is_active": 1},
                ]
            elif "WHERE id = :id FOR UPDATE" in sql:
                result.mappings.return_value.first.return_value = {
                    "id": "a1", "role": "admin", "is_active": 1
                }
            elif "RELEASE_LOCK" in sql:
                release_call_count[0] += 1
                raise RuntimeError("Simulated RELEASE_LOCK failure")
            return result

        conn.execute.side_effect = _execute
        engine = _make_engine_with_conn(conn)

        # Should succeed (UPDATE and RELEASE_LOCK failure handled in finally)
        result = update_user_role_or_status(engine, "a1", new_role="pharmacist", actor_user_id="a2")
        self.assertEqual(result["status"], "updated")

        # RELEASE_LOCK was attempted
        self.assertGreaterEqual(release_call_count[0], 1)
        # conn.invalidate() must be called after the failed release
        conn.invalidate.assert_called_once()


# ===========================================================================
# PROVISION INITIAL ADMIN TESTS
# ===========================================================================

class TestProvisionInitialAdmin(unittest.TestCase):
    """Offline unit tests for provision_initial_admin()."""

    def _build_engine(self, lock_return, existing_admins, target_user):
        conn = MagicMock()
        trans = MagicMock()
        trans.is_active = True
        conn.begin.return_value = trans
        executed = []

        def _execute(stmt, params=None):
            sql = str(stmt)
            executed.append((sql, params))
            result = MagicMock()
            if "GET_LOCK" in sql:
                result.scalar.return_value = lock_return
            elif "WHERE role = 'admin' AND is_active = TRUE FOR UPDATE" in sql:
                result.mappings.return_value.all.return_value = existing_admins
            elif "WHERE email = :email FOR UPDATE" in sql:
                result.mappings.return_value.first.return_value = target_user
            return result

        conn.execute.side_effect = _execute
        conn._executed = executed
        engine = _make_engine_with_conn(conn)
        return engine, conn

    def test_lock_timeout_returns_rolled_back(self):
        engine, _ = self._build_engine(0, [], None)
        res = provision_initial_admin(engine, "admin@example.com")
        self.assertEqual(res["outcome"], InitialAdminOutcome.ROLLED_BACK.value)
        self.assertIn("timed out", res["error"])

    def test_lock_null_returns_rolled_back(self):
        engine, _ = self._build_engine(None, [], None)
        res = provision_initial_admin(engine, "admin@example.com")
        self.assertEqual(res["outcome"], InitialAdminOutcome.ROLLED_BACK.value)

    def test_existing_admin_rejected_and_transaction_rolled_back(self):
        existing = [{"id": "existing-a", "email": "existing@example.com"}]
        engine, conn = self._build_engine(1, existing, None)
        res = provision_initial_admin(engine, "new@example.com")
        self.assertEqual(res["outcome"], InitialAdminOutcome.ROLLED_BACK.value)
        self.assertIn("already exist", res["error"])
        # Transaction must have been explicitly rolled back
        conn.begin.return_value.rollback.assert_called_once()

    def test_missing_target_account_rejected_and_transaction_rolled_back(self):
        engine, conn = self._build_engine(1, [], None)  # target_user=None
        res = provision_initial_admin(engine, "missing@example.com")
        self.assertEqual(res["outcome"], InitialAdminOutcome.ROLLED_BACK.value)
        self.assertIn("does not exist", res["error"])
        conn.begin.return_value.rollback.assert_called_once()

    def test_success_returns_committed(self):
        target = {
            "id": "user-uuid",
            "email": "first@example.com",
            "role": "pharmacist",
            "is_active": 0,
        }
        engine, conn = self._build_engine(1, [], target)
        res = provision_initial_admin(engine, "first@example.com")
        self.assertEqual(res["outcome"], InitialAdminOutcome.COMMITTED.value)
        self.assertEqual(res["user_id"], "user-uuid")
        self.assertIn("operation_id", res)
        self.assertIn("audit_id", res)

    def test_success_releases_lock(self):
        target = {
            "id": "user-uuid",
            "email": "first@example.com",
            "role": "pharmacist",
            "is_active": 0,
        }
        engine, conn = self._build_engine(1, [], target)
        provision_initial_admin(engine, "first@example.com")
        release_calls = [s for s, _ in conn._executed if "RELEASE_LOCK" in s]
        self.assertGreaterEqual(len(release_calls), 1)

    def test_commit_exception_returns_ambiguous(self):
        """If trans.commit() raises, the outcome must be AMBIGUOUS, never ROLLED_BACK."""
        target = {
            "id": "user-uuid",
            "email": "first@example.com",
            "role": "pharmacist",
            "is_active": 0,
        }
        engine, conn = self._build_engine(1, [], target)
        # Make trans.commit() raise after commit_attempted is set True
        conn.begin.return_value.commit.side_effect = RuntimeError("Network timeout during commit")

        res = provision_initial_admin(engine, "first@example.com")
        self.assertEqual(res["outcome"], InitialAdminOutcome.AMBIGUOUS.value)
        self.assertIn("Verify database state", res["error"])

    def test_audit_excludes_sensitive_data(self):
        target = {
            "id": "user-uuid",
            "email": "first@example.com",
            "role": "pharmacist",
            "is_active": 0,
        }
        engine, conn = self._build_engine(1, [], target)
        provision_initial_admin(engine, "first@example.com")

        audit_calls = [(s, p) for s, p in conn._executed if "INSERT INTO audit_logs" in s]
        self.assertEqual(len(audit_calls), 1)
        params = audit_calls[0][1]
        old_data = json.loads(params["old_data"])
        new_data = json.loads(params["new_data"])
        self.assertNotIn("password_hash", old_data)
        self.assertNotIn("password_hash", new_data)


# ===========================================================================
# PROPOSED LIVE MYSQL TESTS (skipped unless authorized)
# ===========================================================================

class TestLiveMySQL(unittest.TestCase):
    """
    STATUS: PROPOSED — skipped unless RUN_LIVE_MYSQL_TESTS=1.
    Requires TEST_DATABASE_URL pointing to a disposable test database (not medishop).

    These tests verify:
    • Two concurrent requests cannot remove the last active administrator.
    • Audit records survive and match committed changes.
    • Connection pool is not contaminated by stale locks after release failures.
    """

    @classmethod
    def setUpClass(cls):
        cls.run_live = os.getenv("RUN_LIVE_MYSQL_TESTS") == "1"
        cls.db_url = os.getenv("TEST_DATABASE_URL", "")

    def _skip_unless_live(self):
        if not self.run_live:
            self.skipTest(
                "Live MySQL test skipped. Set RUN_LIVE_MYSQL_TESTS=1 and TEST_DATABASE_URL "
                "to a disposable test database to enable."
            )

    def _safety_check_url(self):
        """Fails the test if TEST_DATABASE_URL appears to target the real medishop DB."""
        url = self.db_url
        self.assertTrue(url, "TEST_DATABASE_URL must be non-empty.")
        self.assertNotIn("/medishop?", url)
        self.assertFalse(url.rstrip("/").endswith("/medishop"),
                         "TEST_DATABASE_URL must NOT point to the medishop database.")
        self.assertNotIn("medishop_test", url.split("?")[0].split("/")[-1] + "X",
                         "Ensure target database is explicitly disposable.")

    def test_concurrent_last_admin_demotion(self):
        """
        Two threads simultaneously attempt to demote both active admins.
        Exactly one must succeed; exactly one must be rejected with HTTP 403.
        """
        self._skip_unless_live()
        self._safety_check_url()

        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import create_engine
        test_engine = create_engine(self.db_url)

        results, errors = [], []

        def worker(target_id):
            try:
                results.append(update_user_role_or_status(
                    test_engine, target_id, new_role="pharmacist", actor_user_id="test-actor"
                ))
            except HTTPException as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=2) as ex:
            f1 = ex.submit(worker, "test-admin-a")
            f2 = ex.submit(worker, "test-admin-b")
            f1.result()
            f2.result()

        self.assertEqual(len(results), 1, "Exactly one demotion must succeed")
        self.assertEqual(len(errors), 1, "Exactly one demotion must be rejected")
        self.assertEqual(errors[0].status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
