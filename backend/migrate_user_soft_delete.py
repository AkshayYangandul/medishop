"""Idempotently add soft-delete state for user profiles.

Run from ``backend`` with ``python migrate_user_soft_delete.py`` before
deploying application code that filters profiles by ``deleted_at``.
"""

import logging
import sys

from sqlalchemy import text

try:
    from database import engine, DB_NAME
except ImportError:  # Allow running from repository root.
    from backend.database import engine, DB_NAME

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("medishop.migrate_user_soft_delete")


def main() -> int:
    with engine.connect() as conn:
        exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = :db AND table_name = 'profiles' "
                "AND column_name = 'deleted_at'"
            ),
            {"db": DB_NAME},
        ).scalar()
        if exists:
            logger.info("profiles.deleted_at already exists — skipping.")
            return 0
        conn.execute(
            text("ALTER TABLE profiles ADD COLUMN deleted_at DATETIME NULL DEFAULT NULL")
        )
        conn.commit()
        logger.info("Added profiles.deleted_at; existing accounts remain unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
