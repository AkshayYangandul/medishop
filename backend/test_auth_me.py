"""
MediShop authentication identity endpoint tests
=================================================
Offline unit tests for the ``GET /api/auth/me`` handler.

These tests call the FastAPI route handler function directly with a
``current_user`` profile dict, so no HTTP layer or database connection is needed.
Authorization itself (``get_current_user``) is covered by the auth test suite.
"""

import unittest

try:
    from main import get_me
except ImportError:
    from backend.main import get_me


class TestAuthMeEndpoint(unittest.TestCase):
    """Tests for the authenticated identity endpoint GET /api/auth/me."""

    def test_get_me_returns_safe_profile_fields(self):
        """A valid current_user must map to exactly the safe response fields."""
        result = get_me(
            current_user={
                "id": "user-1",
                "email": "pharmacist@medishop.local",
                "full_name": "Dr. John Smith",
                "role": "pharmacist",
                "is_active": True,
            }
        )

        self.assertEqual(result["id"], "user-1")
        self.assertEqual(result["email"], "pharmacist@medishop.local")
        self.assertEqual(result["full_name"], "Dr. John Smith")
        self.assertEqual(result["role"], "pharmacist")
        self.assertTrue(result["is_active"])

    def test_get_me_does_not_expose_credential_material(self):
        """The identity response must never contain password_hash or similar."""
        result = get_me(
            current_user={
                "id": "user-1",
                "email": "pharmacist@medishop.local",
                "full_name": "Dr. John Smith",
                "role": "admin",
                "is_active": True,
            }
        )
        self.assertNotIn("password_hash", result)
        self.assertNotIn("password", result)
        self.assertNotIn("token", result)

    def test_get_me_normalizes_missing_full_name(self):
        """A missing full_name must not cause a KeyError; defaults to empty string."""
        result = get_me(
            current_user={
                "id": "user-2",
                "email": "admin@medishop.local",
                "role": "admin",
                "is_active": True,
            }
        )
        self.assertEqual(result["full_name"], "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
