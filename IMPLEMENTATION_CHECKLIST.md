# MediShop Failed-Login Security Implementation Checklist

- [x] Database: add failed_login_attempts, account_locked, locked_at to profiles (schema.sql + idempotent migration script)
- [x] Apply migration locally to verify compatibility with real MySQL (non-destructive; existing users keep defaults 0/false/NULL)
- [x] email_service.py: add send_account_locked_email (SMTP reuse, escaped HTML, returns bool)
- [x] main.py: rewrite /api/auth/login with row-locked transaction, counter increment, lock transition at 5th failure, email trigger after commit, counter reset on success, locked rejection; add POST /api/users/{user_id}/unlock admin endpoint
- [x] user_service.py: add unlock_user_account service; extend user_list SELECT with lock columns
- [x] frontend api.js: add unlockUserAccount client function
- [x] frontend SettingsPage.jsx: unlock action UI for locked accounts (confirm, loading, success/error, refresh)
- [x] Tests: backend/test_login_security.py (19 mocked unit tests + 1 live-MySQL-gated concurrency test)
- [x] Run new tests + full existing suite; verify no regressions (192 tests OK; 2 live-MySQL tests skipped by default)
- [x] Live MySQL concurrency integration test PASSED against a disposable DB (18 concurrent attempts, threshold enforced, 1 email, locked account rejects correct password)
- [x] Frontend build check (vite build OK)
- [x] Final report
