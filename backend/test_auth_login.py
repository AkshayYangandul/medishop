"""
MediShop authentication login endpoint tests
============================================
Offline unit tests for the ``POST /api/auth/login`` handler.

These tests invoke the FastAPI route handler function directly with mock
database connections (``unittest.mock.MagicMock``), so no HTTP layer or live
MySQL database is required.

Covered behaviours:
- Valid credentials -> signed bearer token + user identity in response.
- Invalid credentials -> HTTP 401 with generic "Invalid email or password.".
- Inactive account    -> HTTP 403 "Forbidden: Account is inactive.".
"""

import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException


def _import_main():
    try:
        import main as main_mod
    except ImportError:
        import backend.main as main_mod
    return main_mod


main = _import_main()
LoginRequest = main.LoginRequest


def _make_engine_with_conn(conn):
    """Returns a mock engine whose context-manager yields ``conn``."""
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    engine.connect.return_value.__exit__.return_value = False
    return engine


def _make_conn_with_profile(profile):
    """Returns a mock connection whose SELECT ... FROM profiles returns ``profile``."""
    conn = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = profile
    conn.execute.return_value = result
    return conn


VALID_PROFILE = {
    "id": "user-1",
    "email": "pharmacist@medishop.local",
    "password_hash": "pbkdf2_sha256$260000$saltedhashvalue$dkvalue",
    "role": "pharmacist",
    "is_active": True,
}

INACTIVE_PROFILE = {
    "id": "user-2",
    "email": "inactive@medishop.local",
    "password_hash": "pbkdf2_sha256$260000$saltedhashvalue$dkvalue",
    "role": "pharmacist",
    "is_active": False,
}


class TestLoginEndpoint(unittest.TestCase):
    """Tests for the authenticated login handler POST /api/auth/login."""

    def test_valid_credentials_return_token_and_user(self):
        """Successful login returns a bearer token and the safe user identity."""
        conn = _make_conn_with_profile(VALID_PROFILE)

        with patch.object(main, "engine", _make_engine_with_conn(conn)), patch.object(
            main, "verify_password", return_value=True
        ):
            result = main.login(
                LoginRequest(email="pharmacist@medishop.local", password="password123")
            )

        self.assertIsInstance(result, dict)
        self.assertTrue(result["access_token"])
        self.assertEqual(result["token_type"], "bearer")
        self.assertEqual(result["user"]["id"], "user-1")
        self.assertEqual(result["user"]["email"], "pharmacist@medishop.local")
        self.assertEqual(result["user"]["role"], "pharmacist")

    def test_invalid_credentials_return_401(self):
        """Wrong password (or unknown email) must yield HTTP 401, not a token."""
        conn = _make_conn_with_profile(VALID_PROFILE)

        with patch.object(main, "engine", _make_engine_with_conn(conn)), patch.object(
            main, "verify_password", return_value=False
        ):
            with self.assertRaises(HTTPException) as ctx:
                main.login(
                    LoginRequest(email="pharmacist@medishop.local", password="wrong-password")
                )

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, "Invalid email or password.")

    def test_inactive_account_returns_403(self):
        """An inactive profile must be rejected even with the correct password."""
        conn = _make_conn_with_profile(INACTIVE_PROFILE)

        with patch.object(main, "engine", _make_engine_with_conn(conn)), patch.object(
            main, "verify_password", return_value=True
        ):
            with self.assertRaises(HTTPException) as ctx:
                main.login(
                    LoginRequest(email="inactive@medishop.local", password="password123")
                )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "Forbidden: Account is inactive.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
