
import sys
import uuid
from getpass import getpass

from sqlalchemy import text

from database import engine
from auth import hash_password
from user_service import provision_initial_admin, InitialAdminOutcome


def main():
    print("\n=== MediShop Initial Admin Setup ===\n")

    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()

    if not full_name or not email or "@" not in email:
        print("Error: Enter a valid name and email.")
        sys.exit(1)

    password = getpass("Create password (minimum 12 characters): ")
    confirm_password = getpass("Confirm password: ")

    if len(password) < 12:
        print("Error: Password must be at least 12 characters.")
        sys.exit(1)

    if password != confirm_password:
        print("Error: Passwords do not match.")
        sys.exit(1)

    # Stop if an active administrator already exists.
    with engine.connect() as conn:
        active_admins = conn.execute(
            text(
                "SELECT COUNT(*) FROM profiles "
                "WHERE role = 'admin' AND is_active = TRUE"
            )
        ).scalar()

        if active_admins:
            print("Setup stopped: An active administrator already exists.")
            sys.exit(1)

        existing_user = conn.execute(
            text("SELECT id FROM profiles WHERE email = :email"),
            {"email": email},
        ).first()

        if existing_user:
            print("Setup stopped: This email already exists.")
            print("No existing account was changed.")
            sys.exit(1)

    # Create an inactive profile first.
    # The provisioning function will promote it to the initial admin.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO profiles "
                "(id, email, password_hash, full_name, role, is_active) "
                "VALUES (:id, :email, :password_hash, :full_name, "
                "'pharmacist', FALSE)"
            ),
            {
                "id": str(uuid.uuid4()),
                "email": email,
                "password_hash": hash_password(password),
                "full_name": full_name,
            },
        )

    # Do not print or store the plaintext password.
    del password
    del confirm_password

    result = provision_initial_admin(
        engine,
        target_email=email,
        operator_notes="Initial administrator setup for local practice project",
    )

    outcome = result.get("outcome")

    if outcome == InitialAdminOutcome.COMMITTED.value:
        print("\nInitial admin setup successful.")

        with engine.connect() as conn:
            profile = conn.execute(
                text(
                    "SELECT id, email, full_name, role, is_active "
                    "FROM profiles WHERE email = :email"
                ),
                {"email": email},
            ).mappings().first()

        if profile:
            print("Name:", profile["full_name"])
            print("Email:", profile["email"])
            print("Role:", profile["role"])
            print("Active:", bool(profile["is_active"]))
            print("\nYou can now try logging in to MediShop.")

    elif outcome == InitialAdminOutcome.AMBIGUOUS.value:
        print("\nWARNING: Provisioning outcome is uncertain.")
        print("Do not rerun the script yet.")
        print("Check the profiles and audit_logs tables first.")
        print("Operation ID:", result.get("operation_id"))
        print("Details:", result.get("error", "Unknown error"))

    else:
        print("\nAdmin setup was not completed.")
        print("Details:", result.get("error", "Unknown error"))
        print("Check the database before retrying.")


if __name__ == "__main__":
    main()
