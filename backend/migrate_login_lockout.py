"""
MediShop: Failed-Login Lockout Migration
=========================================

Idempotent migration that adds failed-login tracking columns to the
``profiles`` table:

* ``failed_login_attempts INT NOT NULL DEFAULT 0``
* ``account_locked  BOOLEAN NOT NULL DEFAULT FALSE``
* ``locked_at       DATETIME NULL DEFAULT NULL``

Existing profile records are left intact; every existing user receives the
safe defaults (zero attempts, not locked, no lock timestamp).

This script does NOT modify or delete any existing data and can be executed
repeatedly — columns that already exist are skipped.

Usage:

    cd backend
    python migrate_login_lockout.py

The script reads the same database configuration as the application
(``backend/.env`` or ``DATABASE_URL``/``DB_*`` environment variables).
"""

import logging
import sys

from sqlalchemy import text

try:
    from database import engine, DB_NAME
except ImportError:  # Allow running from the repository root as well
    from backend.database import engine, DB_NAME

logger = logging.getLogger("medishop.migrate_login_lockout")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

COLUMNS = [
    ("failed_login_attempts", "INT NOT NULL DEFAULT 0"),
    ("account_locked", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("locked_at", "DATETIME NULL DEFAULT NULL"),
]


def column_exists(conn, table: str, column: str) -> bool:
    """Return True when ``table.column`` exists in the connected database."""
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = :db AND table_name = :table AND column_name = :column"
        ),
        {"db": DB_NAME, "table": table, "column": column},
    ).scalar()
    return bool(result)


def main() -> int:
    table = "profiles"
    applied = []

    with engine.connect() as conn:
        for column, definition in COLUMNS:
            if column_exists(conn, table, column):
                logger.info("Column %s.%s already exists — skipping.", table, column)
                continue
            conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )
            )
            conn.commit()
            applied.append(column)
            logger.info("Added column %s.%s (%s).", table, column, definition)

    if applied:
        logger.info("Migration complete. Applied: %s", ", ".join(applied))
    else:
        logger.info("Migration complete. No changes required (already up to date).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
