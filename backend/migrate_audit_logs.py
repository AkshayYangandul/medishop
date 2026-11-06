"""
MediShop: Audit Logs Migration
==============================

Idempotent, additive migration for the existing ``audit_logs`` table.

It adds:

* ``module``       VARCHAR(50) NOT NULL DEFAULT 'system'
* ``description``  VARCHAR(500) NULL
* ``actor_name``   VARCHAR(255) NULL
* ``actor_role``   VARCHAR(20) NULL
* indexes for global, module, and action filtering
* removes the live ``profiles`` foreign key so historical actor IDs survive
  profile deletion

Existing rows are never updated or deleted.  The existing immutability
triggers are left untouched.  The migration can be executed repeatedly.

Usage:

    cd backend
    python migrate_audit_logs.py

Reads the same database configuration as the application (``backend/.env`` or
``DATABASE_URL``/``DB_*`` environment variables).
"""

import logging
import sys

from sqlalchemy import text

try:
    from database import engine, DB_NAME
except ImportError:  # Allow running from the repository root as well
    from backend.database import engine, DB_NAME

logger = logging.getLogger("medishop.migrate_audit_logs")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TABLE = "audit_logs"

COLUMNS = [
    ("module", "VARCHAR(50) NOT NULL DEFAULT 'system' AFTER action"),
    ("description", "VARCHAR(500) NULL AFTER record_id"),
    ("actor_name", "VARCHAR(255) NULL AFTER description"),
    ("actor_role", "VARCHAR(20) NULL AFTER actor_name"),
]

INDEXES = [
    ("idx_audit_logs_created", "created_at DESC"),
    ("idx_audit_logs_module", "module, created_at DESC"),
    ("idx_audit_logs_action", "action, created_at DESC"),
]


def table_exists(conn, table: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = :db AND table_name = :table"
            ),
            {"db": DB_NAME, "table": table},
        ).scalar()
    )


def column_exists(conn, table: str, column: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = :db AND table_name = :table "
                "AND column_name = :column"
            ),
            {"db": DB_NAME, "table": table, "column": column},
        ).scalar()
    )


def index_exists(conn, table: str, index: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.statistics "
                "WHERE table_schema = :db AND table_name = :table "
                "AND index_name = :index"
            ),
            {"db": DB_NAME, "table": table, "index": index},
        ).scalar()
    )


def profile_foreign_keys(conn, table: str) -> list:
    rows = conn.execute(
        text(
            "SELECT constraint_name FROM information_schema.key_column_usage "
            "WHERE table_schema = :db AND table_name = :table "
            "AND column_name = 'user_id' "
            "AND referenced_table_name = 'profiles'"
        ),
        {"db": DB_NAME, "table": table},
    ).all()
    return [row[0] for row in rows]


def main() -> int:
    with engine.connect() as conn:
        if not table_exists(conn, TABLE):
            logger.error("Table %s does not exist in database %s.", TABLE, DB_NAME)
            return 1

        applied = []

        for column, definition in COLUMNS:
            if column_exists(conn, TABLE, column):
                logger.info("Column %s.%s already exists — skipping.", TABLE, column)
                continue
            conn.execute(text(f"ALTER TABLE {TABLE} ADD COLUMN {column} {definition}"))
            conn.commit()
            applied.append(f"column {column}")
            logger.info("Added column %s.%s.", TABLE, column)

        fk_names = profile_foreign_keys(conn, TABLE)
        for fk_name in fk_names:
            conn.execute(text(f"ALTER TABLE {TABLE} DROP FOREIGN KEY `{fk_name}`"))
            conn.commit()
            applied.append(f"foreign key {fk_name}")
            logger.info(
                "Dropped foreign key %s. Historical user_id values are now "
                "immutable actor snapshots.",
                fk_name,
            )
        if not fk_names:
            logger.info("No profiles foreign key on %s.user_id — skipping.", TABLE)

        for index_name, columns in INDEXES:
            if index_exists(conn, TABLE, index_name):
                logger.info("Index %s already exists — skipping.", index_name)
                continue
            conn.execute(text(f"CREATE INDEX {index_name} ON {TABLE} ({columns})"))
            conn.commit()
            applied.append(f"index {index_name}")
            logger.info("Created index %s.", index_name)

    if applied:
        logger.info("Migration complete. Applied: %s", ", ".join(applied))
    else:
        logger.info("Migration complete. No changes required (already up to date).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
