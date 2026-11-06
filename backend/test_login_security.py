"""
MediShop failed-login security tests
====================================

Covers failed-login attempt tracking, account lockout, lockout alert emails,
and administrator-only account unlocking.

These are **offline unit tests**: every SQL call is replaced by
``unittest.mock.MagicMock`` objects, Brevo HTTP requests are mocked (no real email is ever
sent), and no live database is required.

The ``TestLiveMySQLConcurrency`` class contains optional integration tests
against a real (disposable) MySQL database. They run only when
``RUN_LIVE_MYSQL_TESTS=1`` and ``TEST_DATABASE_URL`` (a disposable database,
never the production ``medishop`` database) are set.

Run with:

    cd backend
    python -m unittest test_login_security -v
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Module import (supports running from backend/ or the repository root)
# ---------------------------------------------------------------------------


def _import_main():
    try:
        import main as main_mod
    except ImportError:
        from backend import main as main_mod
    return main_mod


main = _import_main()
LoginRequest = main.LoginRequest
FAILED_LOGIN_ATTEMPT_THRESHOLD = main.FAILED_LOGIN_ATTEMPT_THRESHOLD

try:
    from auth import require_active_admin, get_current_user
except ImportError:
    from backend.auth import require_active_admin, get_current_user

# ---------------------------------------------------------------------------
# Mock connection / engine helpers
# ---------------------------------------------------------------------------


def _make_engine_with_conn(conn):
    """Returns a mock engine whose ``begin()`` and ``connect()`` context
    managers both yield ``conn``.

    Matches ``main.login`` (uses ``engine.connect()`` + explicit transaction)
    and ``user_service.unlock_user_account`` (uses ``engine.begin()``).
    """
    engine = MagicMock()
    for method in ("begin", "connect"):
        getattr(engine, method).return_value.__enter__.return_value = conn
        getattr(engine, method).return_value.__exit__.return_value = False
    return engine


def _make_conn_with_row(row):
    """Returns a mock connection whose SELECT ... FOR UPDATE returns ``row``."""
    conn = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    conn.execute.return_value = result
    return conn


def _update_calls(conn):
    """All UPDATE statements executed on ``conn`` as (sql, params) tuples."""
    calls = []
    for call in conn.execute.call_args_list:
        args = call.args
        if not args:
            continue
        sql = str(args[0])
        if sql.strip().upper().startswith("UPDATE"):
            params = args[1] if len(args) > 1 else {}
            calls.append((sql, params))
    return calls


def _locking_update(conn):
    """The UPDATE that transitions the account to locked, if any."""
    for sql, params in _update_calls(conn):
        if "account_locked = TRUE" in sql:
            return sql, params
    return None


PROFILE_BASE = {
    "id": "user-1",
    "email": "pharmacist@medishop.local",
    "password_hash": "pbkdf2_sha256$260000$salt$value",
    "full_name": "Jane Pharmacist",
    "role": "pharmacist",
    "is_active": True,
}


def unlocked_profile(attempts=0, **overrides):
    row = dict(PROFILE_BASE)
    row["failed_login_attempts"] = attempts
    row["account_locked"] = False
    row["locked_at"] = None
    row.update(overrides)
    return row


def locked_profile(attempts=5):
    row = unlocked_profile(attempts)
    row["account_locked"] = True
    row["locked_at"] = "2026-01-01 10:00:00"
    return row


# ===========================================================================
# Failed login tracking (unit tests, mocked database)
# ===========================================================================

class TestFailedLoginTracking(unittest.TestCase):
    """Per-account failed-attempt counting and lockout transitions."""

    def _login(
        self,
        engine,
        email="pharmacist@medishop.local",
        password="wrong-password",
        email_mock=None,
        warning_mock=None,
    ):
        real_engine = main.engine
        main.engine = engine
        if email_mock is None:
            email_mock = MagicMock(return_value=True)
        if warning_mock is None:
            warning_mock = MagicMock(return_value=True)
        try:
            with patch.object(main, "verify_password", return_value=False), patch.object(
                main, "send_account_locked_email", email_mock
            ), patch.object(main, "send_login_warning_email", warning_mock):
                try:
                    main.login(LoginRequest(email=email, password=password))
                except HTTPException as exc:
                    return exc, email_mock, warning_mock
            raise AssertionError("login should have raised HTTPException")
        finally:
            main.engine = real_engine

    def test_first_incorrect_password_increments_counter_and_stays_unlocked(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=0))
        engine = _make_engine_with_conn(conn)
        exc, email_mock, warning_mock = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.detail, "Invalid email or password.")
        updates = _update_calls(conn)
        self.assertEqual(len(updates), 1)
        sql, params = updates[0]
        self.assertIn("failed_login_attempts = :count", sql)
        self.assertNotIn("account_locked", sql)
        self.assertEqual(params, {"count": 1, "id": "user-1"})
        email_mock.assert_not_called()

    def test_second_incorrect_password_increments_to_two(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=1))
        engine = _make_engine_with_conn(conn)
        exc, _, _ = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        sql, params = _update_calls(conn)[0]
        self.assertEqual(params, {"count": 2, "id": "user-1"})

    def test_third_incorrect_password_increments_to_three(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=2))
        engine = _make_engine_with_conn(conn)
        exc, _, _ = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        sql, params = _update_calls(conn)[0]
        self.assertEqual(params, {"count": 3, "id": "user-1"})

    def test_fourth_incorrect_password_increments_to_four_and_sends_no_email(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=3))
        engine = _make_engine_with_conn(conn)
        exc, email_mock, warning_mock = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        sql, params = _update_calls(conn)[0]
        self.assertEqual(params, {"count": 4, "id": "user-1"})
        self.assertIsNone(_locking_update(conn))
        email_mock.assert_not_called()

    def test_fifth_incorrect_password_locks_account_and_sends_one_email(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=4))
        engine = _make_engine_with_conn(conn)
        exc, email_mock, warning_mock = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.detail, "Invalid email or password.")
        locking = _locking_update(conn)
        self.assertIsNotNone(locking)
        sql, params = locking
        self.assertEqual(params, {"count": 5, "id": "user-1"})
        self.assertIn("locked_at = NOW()", sql)
        email_mock.assert_called_once()
        call_args = email_mock.call_args
        self.assertEqual(call_args.kwargs["to_email"], "pharmacist@medishop.local")
        self.assertEqual(call_args.kwargs["recipient_name"], "Jane Pharmacist")

    def test_locked_account_rejects_further_attempts_without_counting_or_emailing(self):
        conn = _make_conn_with_row(locked_profile(attempts=5))
        engine = _make_engine_with_conn(conn)

        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password") as verify_mock, patch.object(
                main, "send_account_locked_email", return_value=True
            ) as email_mock:
                exc, _, _ = self._login(engine)
        finally:
            main.engine = real_engine

        self.assertEqual(exc.status_code, 401)
        self.assertIn("locked", exc.detail.lower())
        verify_mock.assert_not_called()
        self.assertEqual(_update_calls(conn), [])
        email_mock.assert_not_called()

    def test_locked_account_cannot_log_in_with_correct_password(self):
        conn = _make_conn_with_row(locked_profile(attempts=5))
        engine = _make_engine_with_conn(conn)

        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password", return_value=True), patch.object(
                main, "send_account_locked_email", return_value=True
            ) as email_mock:
                exc, _, _ = self._login(engine)
        finally:
            main.engine = real_engine

        self.assertEqual(exc.status_code, 401)
        self.assertIn("locked", exc.detail.lower())
        self.assertEqual(_update_calls(conn), [])
        email_mock.assert_not_called()

    def test_successful_login_resets_failed_attempt_counter(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=3))
        engine = _make_engine_with_conn(conn)

        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password", return_value=True), patch.object(
                main, "send_account_locked_email", return_value=True
            ) as email_mock:
                result = main.login(
                    LoginRequest(email="pharmacist@medishop.local", password="correct-password")
                )
        finally:
            main.engine = real_engine

        self.assertTrue(result["access_token"])
        self.assertEqual(result["user"]["id"], "user-1")
        updates = _update_calls(conn)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1], {"id": "user-1"})
        email_mock.assert_not_called()

    def test_unknown_email_reveals_nothing_and_counts_nothing(self):
        conn = _make_conn_with_row(None)
        engine = _make_engine_with_conn(conn)
        exc, email_mock, warning_mock = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.detail, "Invalid email or password.")
        self.assertEqual(_update_calls(conn), [])
        email_mock.assert_not_called()

    def test_lockout_email_only_sent_on_transition_to_locked(self):
        """No email on failures 1-4, exactly one on failure 5, none afterwards."""
        email_mock = MagicMock(return_value=True)

        # Failures 1 through 4: no email.
        for attempts in range(0, 4):
            conn = _make_conn_with_row(unlocked_profile(attempts=attempts))
            engine = _make_engine_with_conn(conn)
            exc, _, _ = self._login(
                engine,
                email="x@y.local",
                password="wrong-password",
                email_mock=email_mock,
            )
        self.assertEqual(email_mock.call_count, 0)

        # Failure 5: exactly one email.
        conn = _make_conn_with_row(unlocked_profile(attempts=4))
        engine = _make_engine_with_conn(conn)
        exc, _, _ = self._login(
            engine,
            email="x@y.local",
            password="wrong-password",
            email_mock=email_mock,
        )
        self.assertEqual(email_mock.call_count, 1)

        # Further attempts on the locked account: no repeat email.
        conn = _make_conn_with_row(locked_profile(attempts=5))
        engine = _make_engine_with_conn(conn)
        real_engine = main.engine
        main.engine = engine
        try:
            # verify_password returns True here but must not even be reached;
            # _login patches it to False (wrong password path) which is fine
            # because a locked account is rejected before verification.
            exc, _, _ = self._login(
                engine,
                email="x@y.local",
                password="wrong-password",
                email_mock=email_mock,
            )
        finally:
            main.engine = real_engine
        self.assertEqual(email_mock.call_count, 1)

    def test_email_delivery_failure_does_not_undo_the_lock(self):
        """The account stays locked even when the alert email cannot be delivered."""
        conn = _make_conn_with_row(unlocked_profile(attempts=4))
        engine = _make_engine_with_conn(conn)
        email_mock = MagicMock(return_value=False)

        real_engine = main.engine
        main.engine = engine
        try:
            exc, _, _ = self._login(engine, email_mock=email_mock)
        finally:
            main.engine = real_engine

        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.detail, "Invalid email or password.")
        locking = _locking_update(conn)
        self.assertIsNotNone(locking, "account must still transition to locked")
        email_mock.assert_called_once()


    # ------------------------------------------------------------------
    # Third-attempt warning and fifth-attempt lock notification tests
    # ------------------------------------------------------------------

    def test_admin_receives_warning_at_third_attempt_only(self):
        admin = unlocked_profile(
            attempts=2,
            id="admin-1",
            email="admin@medishop.local",
            full_name="Alex Admin",
            role="admin",
        )
        conn = _make_conn_with_row(admin)
        engine = _make_engine_with_conn(conn)
        exc, lock_mock, warning_mock = self._login(
            engine, email="admin@medishop.local"
        )

        self.assertEqual(exc.status_code, 401)
        warning_mock.assert_called_once()
        kwargs = warning_mock.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "admin@medishop.local")
        self.assertEqual(kwargs["recipient_name"], "Alex Admin")
        self.assertEqual(kwargs["failed_attempts"], 3)
        self.assertEqual(kwargs["remaining_attempts"], 2)
        lock_mock.assert_not_called()
        self.assertIsNone(_locking_update(conn))

    def test_normal_user_receives_warning_at_third_attempt_only(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=2))
        engine = _make_engine_with_conn(conn)
        exc, lock_mock, warning_mock = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        warning_mock.assert_called_once()
        kwargs = warning_mock.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "pharmacist@medishop.local")
        self.assertEqual(kwargs["recipient_name"], "Jane Pharmacist")
        self.assertEqual(kwargs["failed_attempts"], 3)
        self.assertEqual(kwargs["remaining_attempts"], 2)
        lock_mock.assert_not_called()

    def test_warning_is_not_sent_on_first_second_fourth_or_fifth_attempt(self):
        for attempts in (0, 1, 3, 4):
            conn = _make_conn_with_row(unlocked_profile(attempts=attempts))
            engine = _make_engine_with_conn(conn)
            exc, lock_mock, warning_mock = self._login(engine)
            self.assertEqual(exc.status_code, 401)
            warning_mock.assert_not_called()
            if attempts == 4:
                lock_mock.assert_called_once()
            else:
                lock_mock.assert_not_called()

    def test_admin_receives_lock_email_at_fifth_attempt(self):
        admin = unlocked_profile(
            attempts=4,
            id="admin-1",
            email="admin@medishop.local",
            full_name="Alex Admin",
            role="admin",
        )
        conn = _make_conn_with_row(admin)
        engine = _make_engine_with_conn(conn)
        exc, lock_mock, warning_mock = self._login(
            engine, email="admin@medishop.local"
        )

        self.assertEqual(exc.status_code, 401)
        lock_mock.assert_called_once()
        kwargs = lock_mock.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "admin@medishop.local")
        self.assertEqual(kwargs["recipient_name"], "Alex Admin")
        warning_mock.assert_not_called()

    def test_normal_user_receives_lock_email_at_fifth_attempt(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=4))
        engine = _make_engine_with_conn(conn)
        exc, lock_mock, warning_mock = self._login(engine)

        self.assertEqual(exc.status_code, 401)
        lock_mock.assert_called_once()
        kwargs = lock_mock.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "pharmacist@medishop.local")
        self.assertEqual(kwargs["recipient_name"], "Jane Pharmacist")
        warning_mock.assert_not_called()

    def test_recipient_is_always_the_authenticated_accounts_db_email(self):
        """The notification recipient is never a configured provider sender address for
        a different account: it is always the row's own ``email``."""
        profiles = (
            (PROFILE_BASE, "pharmacist@medishop.local"),
            (
                dict(
                    PROFILE_BASE,
                    id="admin-1",
                    email="second.admin@medishop.local",
                    full_name="Second Admin",
                    role="admin",
                ),
                "second.admin@medishop.local",
            ),
        )

        for profile, expected_email in profiles:
            warning_conn = _make_conn_with_row(
                dict(
                    profile,
                    failed_login_attempts=2,
                    account_locked=False,
                    locked_at=None,
                )
            )
            warning_engine = _make_engine_with_conn(warning_conn)
            _, _, warning_mock = self._login(warning_engine, email=expected_email)
            warning_mock.assert_called_once()
            self.assertEqual(
                warning_mock.call_args.kwargs["to_email"], expected_email
            )

            lock_conn = _make_conn_with_row(
                dict(
                    profile,
                    failed_login_attempts=4,
                    account_locked=False,
                    locked_at=None,
                )
            )
            lock_engine = _make_engine_with_conn(lock_conn)
            _, lock_mock, _ = self._login(lock_engine, email=expected_email)
            lock_mock.assert_called_once()
            self.assertEqual(lock_mock.call_args.kwargs["to_email"], expected_email)

    def test_correct_password_does_not_bypass_existing_lock(self):
        conn = _make_conn_with_row(locked_profile(attempts=5))
        engine = _make_engine_with_conn(conn)

        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password", return_value=True) as verify_mock, patch.object(
                main, "send_account_locked_email", return_value=True
            ) as lock_mock, patch.object(
                main, "send_login_warning_email", return_value=True
            ) as warning_mock:
                with self.assertRaises(HTTPException) as ctx:
                    main.login(
                        LoginRequest(
                            email="pharmacist@medishop.local",
                            password="correct-password",
                        )
                    )
        finally:
            main.engine = real_engine

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("locked", ctx.exception.detail.lower())
        # The lock check short-circuits before password verification and no
        # further notification is generated.
        verify_mock.assert_not_called()
        lock_mock.assert_not_called()
        warning_mock.assert_not_called()
        self.assertEqual(_update_calls(conn), [])

    def test_successful_login_resets_counter_and_sends_no_notifications(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=4))
        engine = _make_engine_with_conn(conn)

        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password", return_value=True), patch.object(
                main, "send_account_locked_email", return_value=True
            ) as lock_mock, patch.object(
                main, "send_login_warning_email", return_value=True
            ) as warning_mock:
                result = main.login(
                    LoginRequest(
                        email="pharmacist@medishop.local",
                        password="correct-password",
                    )
                )
        finally:
            main.engine = real_engine

        self.assertTrue(result["access_token"])
        self.assertEqual(result["user"]["id"], "user-1")
        updates = _update_calls(conn)
        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0][1], {"id": "user-1"})
        lock_mock.assert_not_called()
        warning_mock.assert_not_called()

    def test_warning_delivery_failure_does_not_change_login_response(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=2))
        engine = _make_engine_with_conn(conn)
        exc, _, warning_mock = self._login(
            engine, warning_mock=MagicMock(return_value=False)
        )

        self.assertEqual(exc.status_code, 401)
        self.assertEqual(exc.detail, "Invalid email or password.")
        warning_mock.assert_called_once()


class TestSuccessfulLoginPreservesExistingFlow(unittest.TestCase):
    """Existing token creation, role loading, and active-account checks."""

    def test_valid_credentials_return_token_and_user(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=0))
        engine = _make_engine_with_conn(conn)
        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password", return_value=True):
                result = main.login(
                    LoginRequest(email="pharmacist@medishop.local", password="password123")
                )
        finally:
            main.engine = real_engine

        self.assertIsInstance(result, dict)
        self.assertTrue(result["access_token"])
        self.assertEqual(result["token_type"], "bearer")
        self.assertEqual(result["user"]["id"], "user-1")
        self.assertEqual(result["user"]["email"], "pharmacist@medishop.local")
        self.assertEqual(result["user"]["role"], "pharmacist")

    def test_inactive_account_still_rejected_with_403(self):
        row = unlocked_profile(attempts=0)
        row["is_active"] = False
        conn = _make_conn_with_row(row)
        engine = _make_engine_with_conn(conn)
        real_engine = main.engine
        main.engine = engine
        try:
            with patch.object(main, "verify_password", return_value=True):
                with self.assertRaises(HTTPException) as ctx:
                    main.login(
                        LoginRequest(email="inactive@medishop.local", password="password123")
                    )
        finally:
            main.engine = real_engine

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "Forbidden: Account is inactive.")


# ===========================================================================
# Admin-only account unlocking
# ===========================================================================

class TestAdminUnlock(unittest.TestCase):
    """Unlocking requires a verified administrator and resets lock state."""

    def test_authorized_administrator_can_unlock_a_locked_account(self):
        conn = _make_conn_with_row(locked_profile(attempts=5))
        engine = _make_engine_with_conn(conn)

        result = main.unlock_user_account(
            engine=engine,
            target_user_id="user-1",
            actor_user_id="admin-1",
        )

        self.assertEqual(result["status"], "unlocked")
        self.assertFalse(result["account_locked"])
        self.assertEqual(result["failed_login_attempts"], 0)
        self.assertIsNone(result["locked_at"])
        self.assertFalse(result["already_unlocked"])

        updates = _update_calls(conn)
        self.assertEqual(len(updates), 1)
        sql, params = updates[0]
        self.assertIn("account_locked = FALSE", sql)
        self.assertIn("failed_login_attempts = 0", sql)
        self.assertIn("locked_at = NULL", sql)
        self.assertEqual(params, {"id": "user-1"})

    def test_unlocking_already_unlocked_account_is_safe_noop(self):
        conn = _make_conn_with_row(unlocked_profile(attempts=0))
        engine = _make_engine_with_conn(conn)

        result = main.unlock_user_account(
            engine=engine,
            target_user_id="user-1",
            actor_user_id="admin-1",
        )

        self.assertEqual(result["status"], "unlocked")
        self.assertTrue(result["already_unlocked"])
        self.assertEqual(_update_calls(conn), [])

    def test_missing_target_account_returns_404(self):
        conn = _make_conn_with_row(None)
        engine = _make_engine_with_conn(conn)

        with self.assertRaises(HTTPException) as ctx:
            main.unlock_user_account(
                engine=engine,
                target_user_id="does-not-exist",
                actor_user_id="admin-1",
            )

        self.assertEqual(ctx.exception.status_code, 404)

    def test_require_active_admin_rejects_pharmacist(self):
        class FakeUser:
            def get(self, key, default=None):
                return {"role": "pharmacist"}.get(key, default)

        with self.assertRaises(HTTPException) as ctx:
            require_active_admin(FakeUser())
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_active_admin_accepts_admin(self):
        class FakeUser:
            def get(self, key, default=None):
                return {"role": "admin", "id": "admin-1"}.get(key, default)

        result = require_active_admin(FakeUser())
        self.assertEqual(result.get("role"), "admin")

    def test_unauthenticated_request_cannot_authenticate(self):
        with self.assertRaises(HTTPException) as ctx:
            get_current_user(None)
        self.assertEqual(ctx.exception.status_code, 401)


# ===========================================================================
# Optional live-MySQL concurrency integration test
# ===========================================================================

class TestLiveMySQLConcurrency(unittest.TestCase):
    """
    STATUS: PROPOSED — skipped unless RUN_LIVE_MYSQL_TESTS=1.

    Requires TEST_DATABASE_URL pointing to a disposable MySQL database
    (never the production medishop database). Verifies that concurrent
    failed-login requests cannot bypass the fifth-attempt threshold against
    the real row-locked transaction path.
    """

    @classmethod
    def setUpClass(cls):
        cls.run_live = (
            os.getenv("RUN_LIVE_MYSQL_TESTS") == "1"
            and bool(os.getenv("TEST_DATABASE_URL", ""))
        )
        cls.db_url = os.getenv("TEST_DATABASE_URL", "")

    def _skip_unless_live(self):
        if not self.run_live:
            self.skipTest(
                "Live MySQL concurrency test skipped. Set RUN_LIVE_MYSQL_TESTS=1 "
                "and TEST_DATABASE_URL to a disposable test database to enable."
            )

    def _safety_check_url(self):
        url = self.db_url
        self.assertTrue(url, "TEST_DATABASE_URL must be non-empty.")
        self.assertNotIn("/medishop?", url)
        self.assertFalse(url.rstrip("/").endswith("/medishop"))
        self.assertNotIn("medishop", url.split("?")[0].split("/")[-1])

    def _ensure_profiles_table(self, conn):
        """Create the profiles table with lockout columns if missing, or add
        missing columns to an existing table."""
        existing = {
            r[0] for r in conn.execute(
                text("SELECT column_name FROM information_schema.columns "
                     "WHERE table_schema = DATABASE() AND table_name = 'profiles'")
            ).fetchall()
        }
        if not existing:
            conn.execute(
                text(
                    "CREATE TABLE profiles ("
                    "id CHAR(36) NOT NULL, email VARCHAR(255) NOT NULL, "
                    "password_hash VARCHAR(255) NOT NULL, full_name VARCHAR(255) NOT NULL, "
                    "role ENUM('admin','pharmacist') NOT NULL DEFAULT 'pharmacist', "
                    "phone VARCHAR(50), is_active BOOLEAN NOT NULL DEFAULT FALSE, "
                    "failed_login_attempts INT NOT NULL DEFAULT 0, "
                    "account_locked BOOLEAN NOT NULL DEFAULT FALSE, "
                    "locked_at DATETIME NULL DEFAULT NULL, "
                    "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
                    "PRIMARY KEY (id), CONSTRAINT uq_profiles_email UNIQUE (email)) "
                    "ENGINE=InnoDB"
                )
            )
            return

        def add(col_def):
            col_name = col_def.split()[0]
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE profiles ADD COLUMN {col_def}"))

        add("failed_login_attempts INT NOT NULL DEFAULT 0")
        add("account_locked BOOLEAN NOT NULL DEFAULT FALSE")
        add("locked_at DATETIME NULL DEFAULT NULL")

    def test_concurrent_failed_requests_cannot_bypass_threshold(self):
        self._skip_unless_live()
        self._safety_check_url()

        import uuid
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import create_engine, text
        from auth import hash_password

        test_engine = create_engine(self.db_url)
        email_calls = []

        user_id = str(uuid.uuid4())
        email = f"sec-concurrency-{uuid.uuid4().hex[:8]}@example.test"

        try:
            with test_engine.begin() as conn:
                self._ensure_profiles_table(conn)
                conn.execute(
                    text("DELETE FROM profiles WHERE email = :email"),
                    {"email": email},
                )
                conn.execute(
                    text(
                        "INSERT INTO profiles "
                        "(id, email, password_hash, full_name, role, is_active) "
                        "VALUES (:id, :email, :password_hash, 'Stress Test User', 'pharmacist', TRUE)"
                    ),
                    {
                        "id": user_id,
                        "email": email,
                        "password_hash": hash_password("Password123!"),
                    },
                )

            real_engine = main.engine
            main.engine = test_engine
            try:
                with patch.object(main, "verify_password", return_value=False), patch.object(
                    main, "send_account_locked_email",
                    lambda to_email, recipient_name=None: email_calls.append(to_email) or True
                ), patch.object(
                    main, "send_login_warning_email",
                    lambda to_email, recipient_name=None, failed_attempts=3, remaining_attempts=2: True
                ):
                    results = []
                    errors = []

                    def worker():
                        try:
                            for _ in range(3):
                                try:
                                    main.login(
                                        LoginRequest(email=email, password="wrong-password")
                                    )
                                except HTTPException as exc:
                                    results.append(exc.status_code)
                                except Exception as exc:
                                    errors.append(exc)
                        except Exception as exc:
                            errors.append(exc)

                    with ThreadPoolExecutor(max_workers=6) as ex:
                        futures = [ex.submit(worker) for _ in range(6)]
                        for f in futures:
                            f.result()
            finally:
                main.engine = real_engine
            # Every attempt must have been rejected with HTTP 401.
            self.assertEqual(len(results), 18, "all 18 concurrent attempts must complete")
            self.assertTrue(all(code == 401 for code in results), results)
            self.assertEqual(len(errors), 0, errors)

            # Exactly five attempts may have counted; the account must be locked.
            with test_engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT failed_login_attempts, account_locked FROM profiles WHERE email = :email"
                    ),
                    {"email": email},
                ).mappings().first()

            self.assertIsNotNone(row, "test user must still exist")
            self.assertEqual(int(row["failed_login_attempts"]), FAILED_LOGIN_ATTEMPT_THRESHOLD)
            self.assertTrue(bool(row["account_locked"]))

            # Exactly one lockout alert may have been dispatched.
            self.assertEqual(len(email_calls), 1, email_calls)

            # A correct password must not unlock or authenticate the account.
            # Keep main.engine pointed at the test engine so the test user is found.
            main.engine = test_engine
            try:
                with patch.object(main, "verify_password", return_value=True):
                    with self.assertRaises(HTTPException) as ctx:
                        main.login(LoginRequest(email=email, password="Password123!"))
                self.assertEqual(ctx.exception.status_code, 401)
                self.assertIn("locked", ctx.exception.detail.lower())
            finally:
                main.engine = real_engine

        finally:
            try:
                with test_engine.begin() as conn:
                    conn.execute(
                        text("DELETE FROM profiles WHERE email = :email"),
                        {"email": email},
                    )
            finally:
                test_engine.dispose()


if __name__ == "__main__":
    unittest.main(verbosity=2)
