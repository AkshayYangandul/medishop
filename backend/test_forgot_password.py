"""
Unit tests for auth_reset_service.py — Forgot Password feature.

Covers:
- Token generation, hashing, and storage
- Anti-enumeration (always generic response for unknown/inactive/rate-limited)
- Account-based rate limiting (silent, no 429 exposed)
- IP-based rate limiting (silent)
- Token verification (valid, expired, used, invalid)
- Password reset execution (success, replay attack, expiry, short password)
- Single-use / atomic enforcement
- Email delivery failure → token invalidation
- Brevo delivery failure handled safely without leaking token or credentials
"""

import hashlib
import secrets
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
import uuid

# ---------------------------------------------------------------------------
# Minimal stubs so the module can be imported without a real database or auth
# ---------------------------------------------------------------------------

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.strip().encode("utf-8")).hexdigest()


def _make_mapping(**kwargs):
    """Returns a dict-like object compatible with SQLAlchemy RowMapping."""
    return dict(**kwargs)


def _make_conn_returning(rows):
    """
    Builds a minimal SQLAlchemy connection mock whose execute() returns a
    result whose .mappings().first() gives the next value in *rows* (a list).
    scalar() returns the int at the head of rows when it is an int.
    """
    conn = MagicMock()
    results = iter(rows)

    def execute_side_effect(stmt, params=None):
        result = MagicMock()
        try:
            value = next(results)
        except StopIteration:
            value = None

        if isinstance(value, int):
            result.scalar.return_value = value
            result.mappings.return_value.first.return_value = None
        else:
            result.scalar.return_value = 0
            result.mappings.return_value.first.return_value = value

        return result

    conn.execute.side_effect = execute_side_effect
    return conn


class TestHashToken(unittest.TestCase):
    def test_deterministic(self):
        from auth_reset_service import _hash_token
        raw = "test_token_abc"
        self.assertEqual(_hash_token(raw), _hash_token(raw))

    def test_different_tokens_produce_different_hashes(self):
        from auth_reset_service import _hash_token
        self.assertNotEqual(_hash_token("aaa"), _hash_token("bbb"))

    def test_strips_whitespace(self):
        from auth_reset_service import _hash_token
        self.assertEqual(_hash_token("tok"), _hash_token("  tok  "))


class TestResolveClientIp(unittest.TestCase):
    def setUp(self):
        import auth_reset_service
        self._orig = auth_reset_service.TRUSTED_PROXY_NETWORKS
        self.module = auth_reset_service

    def tearDown(self):
        self.module.TRUSTED_PROXY_NETWORKS = self._orig

    def test_no_trusted_proxies_uses_direct_ip(self):
        self.module.TRUSTED_PROXY_NETWORKS = ()
        from auth_reset_service import _resolve_client_ip
        self.assertEqual(_resolve_client_ip("1.2.3.4", "9.9.9.9"), "1.2.3.4")

    def test_trusted_proxy_uses_forwarded_for(self):
        self.module.TRUSTED_PROXY_NETWORKS = ("10.0.0.0",)
        from auth_reset_service import _resolve_client_ip
        self.assertEqual(_resolve_client_ip("10.0.0.1", "5.5.5.5, 10.0.0.1"), "5.5.5.5")

    def test_missing_peer_returns_unknown(self):
        self.module.TRUSTED_PROXY_NETWORKS = ()
        from auth_reset_service import _resolve_client_ip
        self.assertEqual(_resolve_client_ip(None, None), "unknown")


class TestRequestPasswordReset(unittest.TestCase):
    """request_password_reset always returns GENERIC_RESET_RESPONSE."""

    def _run(self, engine, email="user@example.com", client_ip="1.2.3.4"):
        from auth_reset_service import request_password_reset
        return request_password_reset(engine, email, client_ip=client_ip)

    def _generic(self):
        from auth_reset_service import GENERIC_RESET_RESPONSE
        return GENERIC_RESET_RESPONSE

    # -- Helpers ---------------------------------------------------------------

    def _engine_with_user(self, user_row, ip_count=0, account_count=0):
        """
        Returns an engine mock whose begin() context manager produces a conn
        with realistic execute() responses for the standard query sequence:
        ip_count → user_row → account_count → update(invalidate) → insert
        """
        engine = MagicMock()
        conn = MagicMock()

        call_index = {"n": 0}
        sequence = [ip_count, user_row, account_count]

        def execute_side(stmt, params=None):
            idx = call_index["n"]
            call_index["n"] += 1
            result = MagicMock()
            if idx < len(sequence):
                val = sequence[idx]
                if isinstance(val, int):
                    result.scalar.return_value = val
                    result.mappings.return_value.first.return_value = None
                else:
                    result.scalar.return_value = 0
                    result.mappings.return_value.first.return_value = val
            return result

        conn.execute.side_effect = execute_side
        engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
        engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        return engine

    # -- Tests -----------------------------------------------------------------

    def test_nonexistent_email_returns_generic(self):
        engine = self._engine_with_user(None)
        result = self._run(engine)
        self.assertEqual(result, self._generic())

    def test_inactive_user_returns_generic(self):
        user = _make_mapping(id="u1", email="x@x.com", full_name="X", is_active=False)
        engine = self._engine_with_user(user)
        result = self._run(engine)
        self.assertEqual(result, self._generic())

    def test_invalid_email_format_returns_generic(self):
        engine = MagicMock()
        from auth_reset_service import request_password_reset
        result = request_password_reset(engine, "not-an-email")
        self.assertEqual(result, self._generic())
        engine.begin.assert_not_called()

    def test_account_rate_limit_returns_generic_not_429(self):
        """Rate limit must NOT raise 429 — must return generic response."""
        user = _make_mapping(id="u1", email="x@x.com", full_name="X", is_active=True)
        engine = self._engine_with_user(user, ip_count=0, account_count=5)
        result = self._run(engine)
        # Must be generic dict, not an exception
        self.assertEqual(result, self._generic())

    def test_ip_rate_limit_returns_generic(self):
        """IP rate limit must return generic without raising 429."""
        user = _make_mapping(id="u1", email="x@x.com", full_name="X", is_active=True)
        engine = self._engine_with_user(user, ip_count=15, account_count=0)
        result = self._run(engine)
        self.assertEqual(result, self._generic())

    @patch("auth_reset_service.send_password_reset_email", return_value=True)
    def test_valid_user_generates_token_and_returns_generic(self, mock_send):
        user = _make_mapping(id="u1", email="staff@clinic.com", full_name="Alice", is_active=True)
        engine = self._engine_with_user(user, ip_count=0, account_count=0)
        result = self._run(engine, email="staff@clinic.com")
        self.assertEqual(result, self._generic())
        mock_send.assert_called_once()
        # Raw token should NOT be in the response
        self.assertNotIn("token", str(result))

    @patch("auth_reset_service.send_password_reset_email", return_value=False)
    def test_email_delivery_failure_invalidates_token(self, mock_send):
        """When send returns False, an extra DB call must invalidate the token."""
        user = _make_mapping(id="u1", email="staff@clinic.com", full_name="Alice", is_active=True)
        engine = self._engine_with_user(user, ip_count=0, account_count=0)

        # Second engine.begin() call is used to invalidate the undelivered token
        second_conn = MagicMock()
        second_ctx = MagicMock()
        second_ctx.__enter__ = MagicMock(return_value=second_conn)
        second_ctx.__exit__ = MagicMock(return_value=False)

        original_begin = engine.begin.return_value
        engine.begin.side_effect = [original_begin, second_ctx]

        result = self._run(engine, email="staff@clinic.com")
        self.assertEqual(result, self._generic())
        # Invalidation UPDATE must have been called on second conn
        second_conn.execute.assert_called_once()
        sql_text = str(second_conn.execute.call_args[0][0])
        self.assertIn("used_at", sql_text.lower())

    def test_database_error_returns_generic_not_500(self):
        """DB errors must silently return generic — not expose 500 to caller."""
        engine = MagicMock()
        engine.begin.side_effect = Exception("DB connection lost")
        result = self._run(engine)
        self.assertEqual(result, self._generic())


class TestVerifyResetToken(unittest.TestCase):
    def _run(self, engine, token="raw_tok"):
        from auth_reset_service import verify_reset_token
        return verify_reset_token(engine, token)

    def _make_engine(self, row):
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.mappings.return_value.first.return_value = row
        conn.execute.return_value = result
        engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
        engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        return engine

    def test_missing_token_raises_400(self):
        from fastapi import HTTPException
        engine = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine, token="")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invalid_token_hash_raises_400(self):
        from fastapi import HTTPException
        engine = self._make_engine(None)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_already_used_token_raises_400(self):
        from fastapi import HTTPException
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            used_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            email="a@b.com", is_active=True
        )
        engine = self._make_engine(row)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("already been used", ctx.exception.detail)

    def test_expired_token_raises_400(self):
        from fastapi import HTTPException
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            used_at=None,
            email="a@b.com", is_active=True
        )
        engine = self._make_engine(row)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("expired", ctx.exception.detail)

    def test_valid_token_returns_masked_email(self):
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
            used_at=None,
            email="johndoe@example.com", is_active=True
        )
        engine = self._make_engine(row)
        result = self._run(engine)
        self.assertTrue(result["valid"])
        self.assertIn("@example.com", result["email"])
        # Raw email must not appear verbatim
        self.assertNotEqual(result["email"], "johndoe@example.com")

    def test_inactive_account_raises_403(self):
        from fastapi import HTTPException
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=20),
            used_at=None,
            email="a@b.com", is_active=False
        )
        engine = self._make_engine(row)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 403)


class TestExecutePasswordReset(unittest.TestCase):
    def _run(self, engine, token="raw_tok", new_password="newPass1"):
        from auth_reset_service import execute_password_reset
        return execute_password_reset(engine, token, new_password, client_ip="1.2.3.4")

    def _make_engine(self, row):
        engine = MagicMock()
        conn = MagicMock()
        result = MagicMock()
        result.mappings.return_value.first.return_value = row
        conn.execute.return_value = result
        engine.begin.return_value.__enter__ = MagicMock(return_value=conn)
        engine.begin.return_value.__exit__ = MagicMock(return_value=False)
        return engine

    def test_empty_token_raises_400(self):
        from fastapi import HTTPException
        engine = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine, token="")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_short_password_raises_422(self):
        from fastapi import HTTPException
        engine = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine, new_password="abc")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_invalid_token_raises_400(self):
        from fastapi import HTTPException
        engine = self._make_engine(None)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_already_used_token_raises_400(self):
        from fastapi import HTTPException
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            used_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            email="a@b.com", is_active=True
        )
        engine = self._make_engine(row)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_expired_token_raises_400(self):
        from fastapi import HTTPException
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            used_at=None,
            email="a@b.com", is_active=True
        )
        engine = self._make_engine(row)
        with self.assertRaises(HTTPException) as ctx:
            self._run(engine)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("expired", ctx.exception.detail)

    @patch("auth_reset_service.hash_password", return_value="hashed_pw")
    def test_success_updates_password_and_marks_token_used(self, mock_hash):
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=25),
            used_at=None,
            email="a@b.com", is_active=True
        )
        engine = self._make_engine(row)
        result = self._run(engine)
        self.assertIn("successfully reset", result["message"])
        mock_hash.assert_called_once()

        # Verify the conn had UPDATE profiles, UPDATE password_resets (used_at),
        # UPDATE password_resets (invalidate others), INSERT audit_logs
        conn = engine.begin.return_value.__enter__.return_value
        self.assertGreaterEqual(conn.execute.call_count, 4)

    @patch("auth_reset_service.hash_password", return_value="hashed")
    def test_success_response_does_not_leak_token(self, _):
        row = _make_mapping(
            id="r1", user_id="u1",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=25),
            used_at=None,
            email="a@b.com", is_active=True
        )
        engine = self._make_engine(row)
        result = self._run(engine, token="super_secret_token")
        self.assertNotIn("super_secret_token", str(result))


class TestEmailService(unittest.TestCase):
    """Brevo-only dispatcher smoke tests; no real HTTP requests are made."""

    def setUp(self):
        import email_service
        self.email_service = email_service
        self.sender = {
            "from_email": "security@example.test", "from_name": "MediShop Security",
            "reply_to_email": "support@example.test", "is_verified": True,
        }

    def test_sanitize_email_masks_local_part(self):
        self.assertEqual(self.email_service._sanitize_email_for_log("johndoe@example.com"), "j*****e@example.com")

    def test_sanitize_short_local(self):
        result = self.email_service._sanitize_email_for_log("ab@x.com")
        self.assertIn("@x.com", result)

    def test_email_without_active_sender_fails_without_provider_request(self):
        with patch.object(self.email_service, "active_sender", return_value=None), \
             patch.object(self.email_service.urllib.request, "urlopen") as urlopen:
            result = self.email_service.send_password_reset_email("a@b.com", "tok123")
        self.assertFalse(result)
        urlopen.assert_not_called()

    def test_password_reset_template_escapes_recipient_name_and_uses_dispatcher(self):
        captured = {}
        def dispatch(msg, recipient, **kwargs):
            captured["message"] = msg
            captured["recipient"] = recipient
            captured["kwargs"] = kwargs
            return True
        with patch.object(self.email_service, "active_sender", return_value=self.sender), \
             patch.object(self.email_service, "dispatch_transactional_message", side_effect=dispatch) as dispatcher:
            result = self.email_service.send_password_reset_email(
                "dest@example.com", "reset-token", '<script>alert("xss")</script>')
        self.assertTrue(result)
        dispatcher.assert_called_once()
        self.assertEqual(captured["recipient"], "dest@example.com")
        self.assertEqual(captured["kwargs"]["log_description"], "Password reset email")
        self.assertEqual(captured["kwargs"]["config_override"]["from_email"], "security@example.test")
        html_parts = [part.get_payload(decode=True).decode("utf-8") for part in captured["message"].walk()
                      if part.get_content_type() == "text/html"]
        self.assertTrue(html_parts)
        self.assertNotIn("<script>", html_parts[0])
        self.assertIn("&lt;script&gt;", html_parts[0])


if __name__ == "__main__":
    unittest.main()
