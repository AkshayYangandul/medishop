"""
MediShop User-Service
=====================
Handles administrator role and active-status changes, enforcing the
last-active-administrator policy under concurrent requests via a MySQL
session-level named lock (``medishop_admin_role_mutex``).

Locking protocol (same for both public functions)
--------------------------------------------------
1. Check out a **dedicated** connection from the engine pool.
2. Call ``GET_LOCK('medishop_admin_role_mutex', <timeout>)`` on that connection.
   • Returns 1  → lock acquired; proceed.
   • Returns 0  → timeout; reject with 503.
   • Returns NULL / anything else → MySQL error; reject with 500.
3. ``conn.commit()`` to clear the autobegin transaction opened by GET_LOCK,
   ensuring the subsequent explicit transaction starts with a clean snapshot.
4. Open an **explicit** transaction with ``trans = conn.begin()``.
5. Inside the transaction, use ``SELECT … FOR UPDATE`` to lock the exact rows
   being evaluated.  Never use ``SELECT COUNT(*) FOR UPDATE``; locking matching
   rows individually is the correct InnoDB pattern.
6. Commit or roll back the explicit transaction as appropriate.
7. In a **finally** block, call ``RELEASE_LOCK`` on the **same** connection.
   If RELEASE_LOCK itself raises, call ``conn.invalidate()`` so the connection
   is removed from the pool rather than returned with a stale lock.

SQLAlchemy connection-pool safety
----------------------------------
* The ``with engine.connect() as conn:`` context manager returns the connection
  to the pool on exit.  If ``RELEASE_LOCK`` fails and we ``invalidate()`` the
  connection, SQLAlchemy discards it and creates a fresh one next time — the
  lock cannot bleed into another request.
"""

import json
import uuid
import logging
from enum import Enum
from typing import Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.engine import Engine
from fastapi import HTTPException, status

logger = logging.getLogger("medishop.user_service")

ADMIN_ROLE_MUTEX_NAME = "medishop_admin_role_mutex"
MUTEX_TIMEOUT_SECONDS = 5


class InitialAdminOutcome(str, Enum):
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    AMBIGUOUS = "AMBIGUOUS"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _acquire_lock(conn, lock_name: str, timeout: int) -> None:
    """
    Acquires the named MySQL lock on ``conn``.
    Raises HTTPException(503) on timeout, HTTPException(500) on NULL/error.
    After successful acquisition, commits the autobegin transaction so the
    caller can open a clean explicit transaction.
    """
    result = conn.execute(
        text("SELECT GET_LOCK(:name, :timeout)"),
        {"name": lock_name, "timeout": timeout},
    ).scalar()

    if result == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative service is busy. Please retry shortly.",
        )
    if result != 1:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not acquire administrative concurrency lock.",
        )
    # Clear the autobegin transaction opened by GET_LOCK before starting the
    # explicit transaction that will do the real work.
    conn.commit()


def _release_lock(conn, lock_name: str) -> None:
    """
    Releases the named MySQL lock on ``conn``.
    If the release itself raises, the connection is invalidated so it is never
    returned to the pool with a stale lock.
    """
    try:
        conn.execute(
            text("SELECT RELEASE_LOCK(:name)"),
            {"name": lock_name},
        )
        conn.commit()
    except Exception as exc:
        logger.error(
            "RELEASE_LOCK('%s') failed — invalidating connection to prevent pool contamination: %s",
            lock_name, exc,
        )
        try:
            conn.invalidate()
        except Exception:
            pass  # Best-effort; the connection is discarded regardless.


# ---------------------------------------------------------------------------
# update_user_role_or_status
# ---------------------------------------------------------------------------

def update_user_role_or_status(
    engine: Engine,
    target_user_id: str,
    new_role: Optional[str] = None,
    new_is_active: Optional[bool] = None,
    actor_user_id: Optional[str] = None,
    client_ip: str = "127.0.0.1",
    user_agent: str = "MediShop-App",
) -> Dict[str, Any]:
    """
    Atomically updates a staff member's role and/or active status.

    Guarantees:
    • The profile update and its audit-log entry are committed together or not at all.
    • The last active administrator cannot be demoted or deactivated.
    • All concurrent callers are serialised through ``medishop_admin_role_mutex``.
    • The named lock is always released on the same connection that acquired it,
      even on exceptions; if release fails the connection is invalidated.
    • Audit data never contains ``password_hash`` or other credentials.
    • Generic error messages are returned to the client; details are logged server-side.
    """
    # --- Input validation (no DB connection needed) ---
    if new_role is None and new_is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update fields provided. Specify 'role' and/or 'is_active'.",
        )
    if new_role is not None and new_role not in ("admin", "pharmacist"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role '{new_role}'. Must be 'admin' or 'pharmacist'.",
        )

    with engine.connect() as conn:
        _acquire_lock(conn, ADMIN_ROLE_MUTEX_NAME, MUTEX_TIMEOUT_SECONDS)

        trans = conn.begin()
        try:
            # Lock all active-admin rows (individual row locks, not COUNT(*))
            active_admins = conn.execute(
                text(
                    "SELECT id, role, is_active FROM profiles "
                    "WHERE role = 'admin' AND is_active = TRUE FOR UPDATE"
                )
            ).mappings().all()

            # Lock the target profile row
            current_profile = conn.execute(
                text(
                    "SELECT id, role, is_active FROM profiles "
                    "WHERE id = :id FOR UPDATE"
                ),
                {"id": target_user_id},
            ).mappings().first()

            if not current_profile:
                trans.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found.",
                )

            effective_role = new_role if new_role is not None else current_profile["role"]
            effective_is_active = (
                new_is_active if new_is_active is not None else bool(current_profile["is_active"])
            )

            # Last-admin protection
            is_currently_active_admin = (
                current_profile["role"] == "admin" and bool(current_profile["is_active"])
            )
            will_remain_active_admin = effective_role == "admin" and effective_is_active

            if is_currently_active_admin and not will_remain_active_admin:
                if len(active_admins) <= 1:
                    trans.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: Cannot demote or deactivate the last active administrator.",
                    )

            # Apply profile update
            conn.execute(
                text(
                    "UPDATE profiles "
                    "SET role = :role, is_active = :is_active, updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {"role": effective_role, "is_active": effective_is_active, "id": target_user_id},
            )

            # Audit log — same transaction; if this fails the profile update rolls back
            audit_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(id, user_id, action, table_name, record_id, old_data, new_data, ip_address, user_agent) "
                    "VALUES (:audit_id, :actor_id, 'ROLE_OR_STATUS_CHANGE', 'profiles', :target_id, "
                    ":old_data, :new_data, :ip, :ua)"
                ),
                {
                    "audit_id": audit_id,
                    "actor_id": actor_user_id or None,
                    "target_id": target_user_id,
                    "old_data": json.dumps({
                        "role": current_profile["role"],
                        "is_active": bool(current_profile["is_active"]),
                    }),
                    "new_data": json.dumps({
                        "role": effective_role,
                        "is_active": effective_is_active,
                    }),
                    "ip": client_ip,
                    "ua": user_agent,
                },
            )

            trans.commit()

            return {
                "id": target_user_id,
                "role": effective_role,
                "is_active": effective_is_active,
                "status": "updated",
                "audit_id": audit_id,
            }

        except HTTPException:
            if trans.is_active:
                trans.rollback()
            raise
        except Exception as exc:
            if trans.is_active:
                trans.rollback()
            logger.error(
                "Database error during role/status update (target_user_id=%s): %s",
                target_user_id, exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal database error occurred while updating the user profile.",
            )
        finally:
            _release_lock(conn, ADMIN_ROLE_MUTEX_NAME)


# ---------------------------------------------------------------------------
# provision_initial_admin
# ---------------------------------------------------------------------------

def provision_initial_admin(
    engine: Engine,
    target_email: str,
    operator_notes: str = "Initial administrator setup via provisioning CLI",
    client_ip: str = "127.0.0.1",
    user_agent: str = "MediShop-CLI",
) -> Dict[str, Any]:
    """
    Promotes a registered user to the first active administrator.

    The function NEVER automatically promotes the first registered user.
    The caller must supply an explicit ``target_email``.

    Returns a dict with an ``outcome`` key of:
    • ``COMMITTED``   — promotion was confirmed committed.
    • ``ROLLED_BACK`` — the operation was not applied (lock failure, pre-conditions
                        not met, or a pre-commit exception with successful rollback).
    • ``AMBIGUOUS``   — an exception occurred during or after ``trans.commit()``;
                        the caller must verify the database state before acting.
    """
    operation_id = str(uuid.uuid4())
    audit_id = str(uuid.uuid4())

    with engine.connect() as conn:
        # Lock acquisition failures return ROLLED_BACK without opening a transaction.
        lock_result = conn.execute(
            text("SELECT GET_LOCK(:name, :timeout)"),
            {"name": ADMIN_ROLE_MUTEX_NAME, "timeout": MUTEX_TIMEOUT_SECONDS},
        ).scalar()

        if lock_result == 0:
            return {
                "outcome": InitialAdminOutcome.ROLLED_BACK.value,
                "operation_id": operation_id,
                "error": "Named lock acquisition timed out. Another administrative operation is in progress.",
            }
        if lock_result != 1:
            return {
                "outcome": InitialAdminOutcome.ROLLED_BACK.value,
                "operation_id": operation_id,
                "error": "Failed to acquire administrative concurrency lock (MySQL returned NULL).",
            }
        conn.commit()  # Clear autobegin transaction from GET_LOCK

        trans = conn.begin()
        commit_attempted = False
        try:
            # Lock all existing active-admin rows (row locks, not COUNT(*))
            existing_admins = conn.execute(
                text(
                    "SELECT id, email FROM profiles "
                    "WHERE role = 'admin' AND is_active = TRUE FOR UPDATE"
                )
            ).mappings().all()

            if existing_admins:
                trans.rollback()
                return {
                    "outcome": InitialAdminOutcome.ROLLED_BACK.value,
                    "operation_id": operation_id,
                    "error": (
                        f"Provisioning rejected: {len(existing_admins)} active administrator(s) already exist. "
                        "Use update_user_role_or_status to manage existing administrators."
                    ),
                }

            # Lock the target profile row
            target_user = conn.execute(
                text(
                    "SELECT id, email, role, is_active FROM profiles "
                    "WHERE email = :email FOR UPDATE"
                ),
                {"email": target_email},
            ).mappings().first()

            if not target_user:
                trans.rollback()
                return {
                    "outcome": InitialAdminOutcome.ROLLED_BACK.value,
                    "operation_id": operation_id,
                    "error": f"Target user with email '{target_email}' does not exist in profiles.",
                }

            target_id = target_user["id"]

            # Promote the user
            conn.execute(
                text(
                    "UPDATE profiles "
                    "SET role = 'admin', is_active = TRUE, updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {"id": target_id},
            )

            # Audit record in the same transaction
            conn.execute(
                text(
                    "INSERT INTO audit_logs "
                    "(id, user_id, action, table_name, record_id, old_data, new_data, ip_address, user_agent) "
                    "VALUES (:audit_id, :target_id, 'INITIAL_ADMIN_PROVISIONING', 'profiles', :target_id, "
                    ":old_data, :new_data, :ip, :ua)"
                ),
                {
                    "audit_id": audit_id,
                    "target_id": target_id,
                    "old_data": json.dumps({
                        "role": target_user["role"],
                        "is_active": bool(target_user["is_active"]),
                    }),
                    "new_data": json.dumps({
                        "role": "admin",
                        "is_active": True,
                        "operation_id": operation_id,
                        "notes": operator_notes,
                    }),
                    "ip": client_ip,
                    "ua": user_agent,
                },
            )

            commit_attempted = True
            trans.commit()

            return {
                "outcome": InitialAdminOutcome.COMMITTED.value,
                "operation_id": operation_id,
                "audit_id": audit_id,
                "user_id": target_id,
                "email": target_email,
                "message": f"User '{target_email}' promoted to initial active administrator.",
            }

        except Exception as exc:
            logger.error(
                "Error during initial admin provisioning (op_id=%s): %s", operation_id, exc
            )
            if commit_attempted:
                # trans.commit() raised: we cannot claim a confirmed rollback.
                return {
                    "outcome": InitialAdminOutcome.AMBIGUOUS.value,
                    "operation_id": operation_id,
                    "error": (
                        "Commit status is uncertain after an exception. "
                        "Verify database state and audit_logs before retrying."
                    ),
                }
            # Exception occurred before commit_attempted was set.
            if trans.is_active:
                try:
                    trans.rollback()
                    return {
                        "outcome": InitialAdminOutcome.ROLLED_BACK.value,
                        "operation_id": operation_id,
                        "error": "Operation rolled back due to an internal error.",
                    }
                except Exception as rb_exc:
                    logger.error(
                        "Rollback failed for op_id=%s: %s", operation_id, rb_exc
                    )
                    return {
                        "outcome": InitialAdminOutcome.AMBIGUOUS.value,
                        "operation_id": operation_id,
                        "error": (
                            "Rollback failed after an internal error. "
                            "Database state is ambiguous."
                        ),
                    }
            return {
                "outcome": InitialAdminOutcome.AMBIGUOUS.value,
                "operation_id": operation_id,
                "error": "Transaction state is ambiguous after an internal error.",
            }
        finally:
            _release_lock(conn, ADMIN_ROLE_MUTEX_NAME)
