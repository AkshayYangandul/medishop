"""
MediShop: Create a local development test user (non-admin).
============================================================

One-off helper to create a single test profile for verifying failed-login
security behavior.  Reuses the existing password hashing and profile-creation
logic (``auth.hash_password`` and ``user_service.user_create``) — no new
authentication system, no public registration endpoint, no login-page change.

Usage:

    cd backend
    python create_test_user.py

The script prompts interactively for:
  * email address (an address you control)
  * full name
  * password (via ``getpass`` — never echoed, never stored in source)

It creates an active pharmacist (non-admin) profile, verifies the password
hash matches, then reports success.  No existing account is modified and the
admin account is never touched.

Remove the test account afterward with the SQL shown at the end of this file
(or the ``remove_test_user.py`` helper).
"""

import sys
import uuid
from getpass import getpass

from sqlalchemy import text

from database import engine
from auth import hash_password, verify_password
from user_service import user_create

MIN_PASSWORD_LENGTH = 6


def _prompt_email() -> str:
    while True:
        email = input("Email address (one you control): ").strip().lower()
        if not email:
            print("Error: email is required.")
            continue
        if "@" not in email:
            print("Error: enter a valid email address.")
            continue
        return email


def _prompt_full_name() -> str:
    while True:
        name = input("Full name: ").strip()
        if not name:
            print("Error: full name is required.")
            continue
        return name


def _prompt_password() -> str:
    while True:
        password = getpass("Create password (minimum 6 characters): ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"Error: password must be at least {MIN_PASSWORD_LENGTH} characters.")
            continue
        confirm = getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match. Try again.")
            continue
        return password


def email_exists(conn, email: str) -> bool:
    row = conn.execute(
        text("SELECT id FROM profiles WHERE LOWER(email) = LOWER(:email)"),
        {"email": email},
    ).first()
    return row is not None


def verify_created_user(conn, email: str, password: str) -> bool:
    """Confirm the stored hash verifies against the supplied password."""
    row = conn.execute(
        text(
            "SELECT id, email, password_hash, role, is_active, "
            "failed_login_attempts, account_locked, locked_at "
            "FROM profiles WHERE LOWER(email) = LOWER(:email)"
        ),
        {"email": email},
    ).mappings().first()
    if not row:
        return False
    return bool(
        row["is_active"]
        and row["role"] == "pharmacist"
        and not row["account_locked"]
        and int(row["failed_login_attempts"] or 0) == 0
        and row["locked_at"] is None
        and verify_password(password, row["password_hash"])
    )


def main() -> None:
    print("\n=== MediShop: Create Test User (non-admin, pharmacist) ===\n")

    email = _prompt_email()
    full_name = _prompt_full_name()
    password = _prompt_password()

    try:
        with engine.connect() as conn:
            if email_exists(conn, email):
                print(f"\nAborted: an account with email '{email}' already exists.")
                print("No existing account was changed.")
                sys.exit(1)

        payload = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "role": "pharmacist",
            "phone": None,
            "is_active": True,
        }

        created = user_create(engine, payload)

        # Verify the created account can authenticate (hash matches password).
        with engine.connect() as conn:
            ok = verify_created_user(conn, email, password)

        # Never print or persist the plaintext password.
        del password

        if not ok:
            print("\nError: account was created but password verification failed.")
            sys.exit(1)

        print("\nTest user created successfully.")
        print("Name:", created["full_name"])
        print("Email:", created["email"])
        print("Role:", created["role"])
        print("Active:", bool(created["is_active"]))
        print(
            "Login state: unlocked, failed_login_attempts=0, account_locked=FALSE"
        )
        print("\nYou can now use this account to test failed-login lockout behavior.")

    except Exception as exc:  # noqa: BLE001 - surface setup errors to operator
        print(f"\nError: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
