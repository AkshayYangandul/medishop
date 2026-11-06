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

try:
    from auth import hash_password
except ImportError:
    from backend.auth import hash_password

try:
    import audit_service
except ImportError:  # Allow imports from the repository root as well
    import backend.audit_service as audit_service

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
    actor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Atomically updates a staff member's role and/or active status.

    Guarantees:
    • The profile update and its audit-log entry are committed together or not at all.
    • Administrator accounts cannot be deactivated through this API: an active
      administrator must remain active (its role may still be changed, subject to
      the last-active-administrator protection below).
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
                    "WHERE role = 'admin' AND is_active = TRUE AND deleted_at IS NULL FOR UPDATE"
                )
            ).mappings().all()

            # Lock the target profile row
            current_profile = conn.execute(
                text(
                    "SELECT id, full_name, role, is_active FROM profiles "
                    "WHERE id = :id AND deleted_at IS NULL FOR UPDATE"
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

            # Administrator accounts must never be deactivated through the Panel
            # Accounts API.  An active administrator stays active; its role may
            # still be changed (subject to the last-active-administrator
            # protection below), but flipping an administrator account to
            # inactive is rejected outright regardless of how many other
            # administrators exist.
            if effective_role == "admin" and not effective_is_active:
                trans.rollback()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Administrator accounts cannot be deactivated.",
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
            audit_id = audit_service.record_audit(
                conn,
                actor=actor,
                actor_user_id=actor_user_id or None,
                action=audit_service.ACTION_ROLE_OR_STATUS_CHANGE,
                module=audit_service.MODULE_USERS,
                entity_type="profiles",
                entity_id=target_user_id,
                description=(
                    "Updated role/status for "
                    f"'{current_profile.get('full_name') or target_user_id}'"
                ),
                old_values={
                    "role": current_profile["role"],
                    "is_active": bool(current_profile["is_active"]),
                },
                new_values={
                    "role": effective_role,
                    "is_active": effective_is_active,
                },
                ip_address=client_ip,
                user_agent=user_agent,
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
                    "WHERE role = 'admin' AND is_active = TRUE AND deleted_at IS NULL FOR UPDATE"
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
                    "SELECT id, full_name, email, role, is_active FROM profiles "
                    "WHERE email = :email AND deleted_at IS NULL FOR UPDATE"
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
            audit_id = audit_service.record_audit(
                conn,
                actor={
                    "id": target_id,
                    "full_name": target_user.get("full_name"),
                    "role": target_user.get("role"),
                },
                action=audit_service.ACTION_INITIAL_ADMIN_PROVISIONING,
                module=audit_service.MODULE_USERS,
                entity_type="profiles",
                entity_id=target_id,
                description=f"Provisioned initial administrator '{target_email}'",
                old_values={
                    "role": target_user["role"],
                    "is_active": bool(target_user["is_active"]),
                },
                new_values={
                    "role": "admin",
                    "is_active": True,
                    "operation_id": operation_id,
                    "notes": operator_notes,
                },
                ip_address=client_ip,
                user_agent=user_agent,
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


def user_list(engine: Engine) -> list:
    """Returns all non-deleted profiles for account administration.

    Includes failed-login lockout state so authorized administrators can see
    and act on locked accounts.
    """
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                "SELECT id, email, full_name, role, phone, is_active, "
                    "failed_login_attempts, account_locked, locked_at, created_at, updated_at "
                "FROM profiles WHERE deleted_at IS NULL ORDER BY created_at ASC"
                )
            ).mappings().all()
            profiles = [dict(row) for row in rows]
            for profile in profiles:
                # Raw SQL text results return MySQL BOOLEAN/TINYINT values as
                # integers; emit actual JSON booleans for frontend consumers.
                profile["is_active"] = bool(profile.get("is_active"))
                profile["account_locked"] = bool(profile.get("account_locked"))
            return profiles
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while listing users.",
        ) from exc


def unlock_user_account(
    engine: Engine,
    target_user_id: str,
    actor_user_id: Optional[str] = None,
    client_ip: str = "127.0.0.1",
    user_agent: str = "MediShop-App",
    actor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Unlocks a locked user account and resets its failed-login counter.

    Performed inside a single transaction with a row lock:
    1. Find the target profile (HTTP 404 when missing).
    2. Clear ``account_locked`` and ``locked_at``.
    3. Reset ``failed_login_attempts`` to zero.
    4. Commit.

    The user's role, active status, password, and unrelated profile fields are
    never touched. Unlocking an already-unlocked account is a safe no-op that
    still returns the current account state.

    Requires the caller to have already been authorized as an administrator by
    the route dependency (``require_active_admin``); this function performs no
    role check itself.
    """
    if not target_user_id or not str(target_user_id).strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    target_user_id = str(target_user_id).strip()

    with engine.begin() as conn:
        row = conn.execute(
            text(
                "SELECT id, full_name, email, role, account_locked, "
                "failed_login_attempts, locked_at "
                "FROM profiles WHERE id = :id FOR UPDATE"
            ),
            {"id": target_user_id},
        ).mappings().first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found.",
            )

        already_unlocked = not bool(row["account_locked"])

        if not already_unlocked:
            conn.execute(
                text(
                    "UPDATE profiles "
                    "SET account_locked = FALSE, failed_login_attempts = 0, locked_at = NULL, updated_at = NOW() "
                    "WHERE id = :id"
                ),
                {"id": target_user_id},
            )

            # Immutable audit record for the unlock action.
            audit_id = audit_service.record_audit(
                conn,
                actor=actor,
                actor_user_id=actor_user_id or None,
                action=audit_service.ACTION_ACCOUNT_UNLOCK,
                module=audit_service.MODULE_USERS,
                entity_type="profiles",
                entity_id=target_user_id,
                description=(
                    "Unlocked account for "
                    f"'{row.get('full_name') or row.get('email') or target_user_id}'"
                ),
                old_values={
                    "account_locked": True,
                    "failed_login_attempts": int(row["failed_login_attempts"] or 0),
                    "locked_at": str(row["locked_at"]) if row["locked_at"] is not None else None,
                },
                new_values={
                    "account_locked": False,
                    "failed_login_attempts": 0,
                    "locked_at": None,
                },
                ip_address=client_ip,
                user_agent=user_agent,
            )

    return {
        "id": target_user_id,
        "account_locked": False,
        "failed_login_attempts": 0,
        "locked_at": None,
        "status": "unlocked",
        "already_unlocked": already_unlocked,
        "audit_id": audit_id if not already_unlocked else None,
    }


# ---------------------------------------------------------------------------
# delete_user_account
# ---------------------------------------------------------------------------

# Keep profiles as historical actor identities. Business tables and audit logs
# continue referencing the original row; only credentials/access are retired.
def delete_user_account(
    engine: Engine,
    target_user_id: str,
    actor_user_id: Optional[str] = None,
    client_ip: str = "127.0.0.1",
    user_agent: str = "MediShop-App",
    actor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Soft-deletes a staff account without removing its historical identity.

    Safeguards (all enforced inside one explicit transaction while holding the
    administrative named lock):
    • 404 when the target profile does not exist.
    • 403 when an administrator targets their own account.
    • 403 when the target is the last active administrator.
    • Preserve all business and audit references by retaining the profile row.
    • Mark it deleted/inactive, lock it, reset failed-login state, and remove
      transient password-reset tokens.
    • The profile update and audit entry commit together or roll back
      together.

    Requires the caller to have already been authorized as an active
    administrator by the route dependency (``require_active_admin``).
    """
    if not target_user_id or not str(target_user_id).strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found.",
        )

    target_user_id = str(target_user_id).strip()
    actor_id = str(actor_user_id).strip() if actor_user_id else None

    with engine.connect() as conn:
        _acquire_lock(conn, ADMIN_ROLE_MUTEX_NAME, MUTEX_TIMEOUT_SECONDS)

        trans = conn.begin()
        try:
            # Verify existence and lock the target row.
            target = conn.execute(
                text(
                    "SELECT id, email, full_name, role, is_active "
                    "FROM profiles WHERE id = :id AND deleted_at IS NULL FOR UPDATE"
                ),
                {"id": target_user_id},
            ).mappings().first()

            if not target:
                trans.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found.",
                )

            # Self-deletion is never allowed.
            if actor_id is not None and target_user_id == actor_id:
                trans.rollback()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You cannot delete your own account.",
                )

            # Always retain at least one active administrator.
            if target["role"] == "admin" and bool(target["is_active"]):
                active_admins = conn.execute(
                    text(
                        "SELECT id FROM profiles "
                        "WHERE role = 'admin' AND is_active = TRUE "
                        "AND deleted_at IS NULL FOR UPDATE"
                    )
                ).mappings().all()
                if len(active_admins) <= 1:
                    trans.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "Forbidden: Cannot delete the last active "
                            "administrator."
                        ),
                    )

            # Reset tokens are ephemeral credentials, not business history.
            conn.execute(
                text("DELETE FROM password_resets WHERE user_id = :id"),
                {"id": target_user_id},
            )

            conn.execute(
                text(
                    "UPDATE profiles SET deleted_at = NOW(), is_active = FALSE, "
                    "account_locked = TRUE, failed_login_attempts = 0, locked_at = NULL, "
                    "updated_at = NOW() WHERE id = :id AND deleted_at IS NULL"
                ),
                {"id": target_user_id},
            )

            # Audit record in the same transaction.  Audit entries are
            # immutable and only ever inserted; this one records the acting
            # administrator and the deleted account's non-sensitive identity.
            audit_id = audit_service.record_audit(
                conn,
                actor=actor,
                actor_user_id=actor_id,
                action=audit_service.ACTION_ACCOUNT_DELETE,
                module=audit_service.MODULE_USERS,
                entity_type="profiles",
                entity_id=target_user_id,
                description=(
                    "Soft-deleted account for "
                    f"'{target.get('full_name') or audit_service.mask_email(target.get('email')) or target_user_id}'"
                ),
                old_values={
                    "email": audit_service.mask_email(target.get("email")),
                    "full_name": target.get("full_name"),
                    "role": target.get("role"),
                    "is_active": bool(target.get("is_active")),
                },
                new_values={"deleted": True, "is_active": False, "account_locked": True},
                ip_address=client_ip,
                user_agent=user_agent,
            )

            trans.commit()

            return {
                "id": target_user_id,
                "email": target["email"],
                "status": "deleted",
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
                "Database error during account deletion (target_user_id=%s): %s",
                target_user_id, exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal database error occurred while deleting the user profile.",
            )
        finally:
            _release_lock(conn, ADMIN_ROLE_MUTEX_NAME)


def restore_user_account(
    engine: Engine,
    email: str,
    *,
    actor_user_id: str,
    actor: Optional[Dict[str, Any]] = None,
    client_ip: str = "127.0.0.1",
    user_agent: str = "MediShop-App",
) -> Dict[str, Any]:
    """Restores a soft-deleted profile without enabling login or changing its password."""
    clean_email = str(email or "").strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid email address is required.",
        )

    with engine.begin() as conn:
        profile = conn.execute(
            text(
                "SELECT id, email, full_name, role, deleted_at FROM profiles "
                "WHERE LOWER(email) = :email FOR UPDATE"
            ),
            {"email": clean_email},
        ).mappings().first()

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No deleted account exists for this email address.",
            )
        if profile["deleted_at"] is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active account already uses this email address.",
            )

        conn.execute(
            text(
                "UPDATE profiles SET deleted_at = NULL, is_active = FALSE, "
                "account_locked = FALSE, failed_login_attempts = 0, locked_at = NULL, "
                "updated_at = NOW() WHERE id = :id AND deleted_at IS NOT NULL"
            ),
            {"id": profile["id"]},
        )

        audit_id = audit_service.record_audit(
            conn,
            actor=actor,
            actor_user_id=actor_user_id,
            action=audit_service.ACTION_ACCOUNT_RESTORE,
            module=audit_service.MODULE_USERS,
            entity_type="profiles",
            entity_id=profile["id"],
            description=f"Restored soft-deleted account for '{profile['full_name']}'; account remains inactive",
            old_values={"deleted": True},
            new_values={
                "deleted": False,
                "is_active": False,
                "account_locked": False,
                "failed_login_attempts": 0,
            },
            ip_address=client_ip,
            user_agent=user_agent,
        )

    return {
        "id": profile["id"],
        "email": profile["email"],
        "full_name": profile["full_name"],
        "role": profile["role"],
        "is_active": False,
        "status": "restored",
        "audit_id": audit_id,
    }


def user_create(
    engine: Engine,
    payload: Dict[str, Any],
    created_by: Optional[str] = None,
    *,
    actor: Optional[Dict[str, Any]] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates a new user profile with hashed password.
    Validates email uniqueness and valid role ('admin', 'pharmacist').
    """
    email = str(payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A valid email address is required.",
        )
    password = str(payload.get("password") or "")
    if len(password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 6 characters.",
        )
    full_name = str(payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name is required.",
        )
    role = str(payload.get("role") or "pharmacist").strip().lower()
    if role not in ("admin", "pharmacist"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid role. Must be 'admin' or 'pharmacist'.",
        )
    phone = payload.get("phone")
    is_active = bool(payload.get("is_active") if "is_active" in payload else True)

    hashed = hash_password(password)
    user_id = str(uuid.uuid4())

    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id, deleted_at FROM profiles WHERE LOWER(email) = LOWER(:email)"),
                {"email": email},
            ).mappings().first()
            if existing:
                if existing["deleted_at"] is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "A deleted account already uses this email address. "
                            "Confirm restoration to reuse it."
                        ),
                    )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A user with this email address already exists.",
                )

            conn.execute(
                text(
                    "INSERT INTO profiles (id, email, password_hash, full_name, role, phone, is_active) "
                    "VALUES (:id, :email, :password_hash, :full_name, :role, :phone, :is_active)"
                ),
                {
                    "id": user_id,
                    "email": email,
                    "password_hash": hashed,
                    "full_name": full_name,
                    "role": role,
                    "phone": phone,
                    "is_active": is_active,
                },
            )

            row = conn.execute(
                text(
                    "SELECT id, email, full_name, role, phone, is_active, created_at, updated_at "
                    "FROM profiles WHERE id = :user_id"
                ),
                {"user_id": user_id},
            ).mappings().first()
            result = dict(row)
            audit_service.record_audit(
                conn,
                actor=actor,
                actor_user_id=created_by,
                action=audit_service.ACTION_USER_CREATED,
                module=audit_service.MODULE_USERS,
                entity_type="profiles",
                entity_id=user_id,
                description=f"Created user account for '{result.get('full_name') or email}'",
                new_values={
                    "email": audit_service.mask_email(result.get("email")),
                    "full_name": result.get("full_name"),
                    "role": result.get("role"),
                    "phone": audit_service.mask_phone(result.get("phone")),
                    "is_active": result.get("is_active"),
                },
                ip_address=client_ip,
                user_agent=user_agent,
            )
            return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating the user.",
        ) from exc
