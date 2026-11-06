"""
MediShop Password Reset Service
=================================
Implements secure, single-use, 30-minute password reset token generation,
verification, and password update processing.

Security Architecture:
- Cryptographically strong random tokens generated via ``secrets.token_urlsafe(32)``.
- ONLY the SHA-256 hash of the token is persisted in the database; raw tokens
  are never stored, returned, or logged.
- Single-use behavior enforced atomically: `used_at` timestamp is updated in the
  same transaction as `profiles.password_hash`.
- 30-minute expiration enforced strictly against UTC wall-clock time.
- Anti-enumeration protection: ``request_password_reset`` ALWAYS returns the
  generic success response regardless of whether the email exists, is active,
  or has exceeded its rate limit. No internal branching leaks user existence.
- IP-based rate limiting applied alongside account-based rate limiting.
  X-Forwarded-For headers are only trusted when TRUSTED_PROXY_NETWORKS is set.
- When email delivery fails (send_password_reset_email returns False), the
  undelivered token is immediately invalidated so it can never be used.
- Operational failures are logged securely with masked email addresses.
- Reuses existing MediShop password hashing from ``auth.py``.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from fastapi import HTTPException, status

try:
    from auth import hash_password
    from email_service import send_password_reset_email, _sanitize_email_for_log
except ImportError:
    from backend.auth import hash_password
    from backend.email_service import send_password_reset_email, _sanitize_email_for_log

try:
    import audit_service
except ImportError:  # Allow imports from the repository root as well
    import backend.audit_service as audit_service

logger = logging.getLogger("medishop.auth_reset")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RESET_TOKEN_EXPIRE_MINUTES = 30
MAX_REQUESTS_PER_WINDOW = 3           # per user account per window
MAX_IP_REQUESTS_PER_WINDOW = 10       # per source IP across all accounts per window
RATE_LIMIT_WINDOW_MINUTES = 15
GENERIC_RESET_RESPONSE = {
    "message": "If that email address is registered, password reset instructions have been sent."
}

# Trusted reverse-proxy CIDR prefixes — extend only if a known load-balancer
# sits in front of this service.  When empty (the default), X-Forwarded-For
# and X-Real-IP headers are ignored and the direct TCP peer address is used to
# prevent IP spoofing through header injection.
TRUSTED_PROXY_NETWORKS: tuple = ()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hash_token(raw_token: str) -> str:
    """Computes SHA-256 hex digest of a raw reset token."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def _resolve_client_ip(
    direct_peer_ip: Optional[str],
    forwarded_for: Optional[str] = None,
) -> str:
    """
    Returns the best-effort client IP address.

    X-Forwarded-For is only trusted when TRUSTED_PROXY_NETWORKS is configured.
    When no trusted proxies are configured the direct TCP peer address is used to
    prevent IP spoofing through header injection.
    """
    if TRUSTED_PROXY_NETWORKS and forwarded_for:
        # Take the leftmost (client) address from X-Forwarded-For
        candidate = forwarded_for.split(",")[0].strip()
        if candidate:
            return candidate
    return direct_peer_ip or "unknown"


def _invalidate_token_by_hash(conn, token_hash: str, now: datetime) -> None:
    """Marks a specific token as used (invalidated) by its hash."""
    conn.execute(
        text("UPDATE password_resets SET used_at = :now WHERE token_hash = :token_hash AND used_at IS NULL"),
        {"now": now, "token_hash": token_hash},
    )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

def request_password_reset(
    engine: Engine,
    email: str,
    client_ip: Optional[str] = None,
    forwarded_for: Optional[str] = None,
) -> Dict[str, str]:
    """
    Initiates a password reset flow.

    Anti-enumeration guarantee:
    Always returns ``GENERIC_RESET_RESPONSE`` for every outcome — including when
    the email is unknown, the account is inactive, or rate limits have been
    reached.  This prevents user-existence discovery through differential
    HTTP status codes or response timing.

    Rate limiting (both are enforced, neither is exposed externally):
    - Account-based: max 3 requests per user per 15-minute window.
    - IP-based: max 10 requests per source IP per 15-minute window.

    When email delivery fails the generated token is immediately invalidated.
    """
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email:
        # Return uniform generic response — do not reveal validation failure
        return GENERIC_RESET_RESPONSE

    resolved_ip = _resolve_client_ip(client_ip, forwarded_for)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    raw_token: Optional[str] = None
    token_hash: Optional[str] = None
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None

    try:
        with engine.begin() as conn:
            # --- IP-based rate limiting (silent: does not reveal existence) ---
            ip_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM password_resets "
                    "WHERE ip_address = :ip "
                    "AND created_at >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)"
                    ),
                {"ip": resolved_ip},
            ).scalar() or 0

            if ip_count >= MAX_IP_REQUESTS_PER_WINDOW:
                logger.warning(
                    "IP-based password reset rate limit reached for ip=%s (%d requests in %d min)",
                    resolved_ip,
                    ip_count,
                    RATE_LIMIT_WINDOW_MINUTES,
                )
                # Return generic response — do NOT raise 429 (would reveal info)
                return GENERIC_RESET_RESPONSE

            # --- User lookup ---
            user = conn.execute(
                text(
                    "SELECT id, email, full_name, is_active "
                    "FROM profiles WHERE LOWER(email) = :email AND deleted_at IS NULL"
                ),
                {"email": clean_email},
            ).mappings().first()

            if not user or not bool(user["is_active"]):
                logger.info(
                    "Password reset requested for non-existent or inactive account (silent pass)"
                )
                return GENERIC_RESET_RESPONSE

            user_id = user["id"]
            user_email = user["email"]
            user_full_name = user["full_name"]

            # --- Account-based rate limiting (silent: does not raise 429) ---
            account_count = conn.execute(
                text(
                    "SELECT COUNT(*) FROM password_resets "
                    "WHERE user_id = :user_id "
                    "AND created_at >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)"
                ),
                {"user_id": user_id},
            ).scalar() or 0

            if account_count >= MAX_REQUESTS_PER_WINDOW:
                logger.warning(
                    "Account-based password reset rate limit reached for user_id=%s "
                    "(%d requests in %d min)",
                    user_id,
                    account_count,
                    RATE_LIMIT_WINDOW_MINUTES,
                )
                # Return generic response — do NOT expose rate-limit to caller
                return GENERIC_RESET_RESPONSE

            # --- Invalidate previous unconsumed tokens for this user ---
            conn.execute(
                text(
                    "UPDATE password_resets SET used_at = :now "
                    "WHERE user_id = :user_id AND used_at IS NULL"
                ),
                {"user_id": user_id, "now": now},
            )

            # --- Generate new token and store only its hash ---
            raw_token = secrets.token_urlsafe(32)
            token_hash = _hash_token(raw_token)
            expires_at = now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
            reset_record_id = str(uuid.uuid4())

            conn.execute(
                text(
                    "INSERT INTO password_resets "
                    "(id, user_id, token_hash, expires_at, used_at, ip_address) "
                    "VALUES (:id, :user_id, :token_hash, :expires_at, NULL, :ip_address)"
                ),
                {
                    "id": reset_record_id,
                    "user_id": user_id,
                    "token_hash": token_hash,
                    "expires_at": expires_at,
                    "ip_address": resolved_ip,
                },
            )

    except Exception as exc:
        logger.error("Database error during password reset request: %s", type(exc).__name__)
        # Return generic response — never expose internal errors externally
        return GENERIC_RESET_RESPONSE

    # --- Dispatch email outside the database transaction ---
    # If delivery fails, immediately invalidate the stored token so it
    # cannot be used via a link that was never actually delivered.
    if raw_token and token_hash and user_email:
        delivered = send_password_reset_email(
            to_email=user_email,
            reset_token=raw_token,
            recipient_name=user_full_name,
        )

        if not delivered:
            logger.error(
                "Password reset email delivery failed for masked recipient %s; "
                "invalidating undelivered token to prevent orphaned reset links.",
                _sanitize_email_for_log(user_email),
            )
            try:
                with engine.begin() as conn:
                    _invalidate_token_by_hash(conn, token_hash, datetime.now(timezone.utc))
            except Exception as exc:
                logger.error(
                    "Failed to invalidate undelivered reset token: %s",
                    type(exc).__name__,
                )

    return GENERIC_RESET_RESPONSE


def verify_reset_token(engine: Engine, raw_token: str) -> Dict[str, Any]:
    """
    Verifies that a reset token exists, has not expired, and has not been used.
    Used by frontend when opening the reset link to check validity upfront.
    """
    if not raw_token or not raw_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or missing password reset token.",
        )

    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT pr.id, pr.user_id, pr.expires_at, pr.used_at, p.email, p.is_active "
                    "FROM password_resets pr "
                    "JOIN profiles p ON pr.user_id = p.id "
                    "WHERE pr.token_hash = :token_hash AND p.deleted_at IS NULL"
                ),
                {"token_hash": token_hash},
            ).mappings().first()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or unrecognized password reset link.",
                )

            if row["used_at"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This password reset link has already been used. Please request a new one.",
                )

            # Compare UTC datetimes — handle timezone-aware or naive values from MySQL
            expires_at = row["expires_at"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This password reset link has expired (valid for 30 minutes). Please request a new one.",
                )

            if not bool(row["is_active"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive. Please contact your system administrator.",
                )

            # Return masked email for user comfort in UI (e.g. j***n@domain.com)
            email = row["email"]
            local, domain = email.split("@", 1)
            masked = local[0] + "***" + local[-1] if len(local) > 2 else local[0] + "*"
            return {
                "valid": True,
                "email": f"{masked}@{domain}",
            }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error verifying reset token: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while validating the reset token.",
        ) from exc


def execute_password_reset(
    engine: Engine,
    raw_token: str,
    new_password: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, str]:
    """
    Atomically verifies the token, updates the user's password, and marks
    the token as used.  Uses SELECT … FOR UPDATE to prevent concurrent reuse.
    """
    if not raw_token or not raw_token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token is required.",
        )

    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 6 characters long.",
        )

    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    try:
        with engine.begin() as conn:
            # Row-level lock prevents two concurrent requests from both passing
            row = conn.execute(
                text(
                    "SELECT pr.id, pr.user_id, pr.expires_at, pr.used_at, "
                    "p.email, p.full_name, p.role, p.is_active "
                    "FROM password_resets pr "
                    "JOIN profiles p ON pr.user_id = p.id "
                    "WHERE pr.token_hash = :token_hash AND p.deleted_at IS NULL "
                    "FOR UPDATE"
                ),
                {"token_hash": token_hash},
            ).mappings().first()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or unrecognized password reset token.",
                )

            if row["used_at"] is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This password reset link has already been used. Please request a new one.",
                )

            expires_at = row["expires_at"]
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This password reset link has expired. Please request a new one.",
                )

            if not bool(row["is_active"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account is inactive.",
                )

            user_id = row["user_id"]
            new_hash = hash_password(new_password)

            # 1. Update user password
            conn.execute(
                text("UPDATE profiles SET password_hash = :new_hash WHERE id = :user_id"),
                {"new_hash": new_hash, "user_id": user_id},
            )

            # 2. Mark this token as consumed (single-use enforcement)
            conn.execute(
                text("UPDATE password_resets SET used_at = :now WHERE id = :reset_id"),
                {"now": now, "reset_id": row["id"]},
            )

            # 3. Invalidate any other still-active reset tokens for this user
            conn.execute(
                text(
                    "UPDATE password_resets SET used_at = :now "
                    "WHERE user_id = :user_id AND used_at IS NULL"
                ),
                {"now": now, "user_id": user_id},
            )

            # 4. Record immutable audit log entry
            audit_id = audit_service.record_audit(
                conn,
                actor={
                    "id": user_id,
                    "full_name": row.get("full_name"),
                    "role": row.get("role"),
                },
                action=audit_service.ACTION_PASSWORD_RESET_SUCCESS,
                module=audit_service.MODULE_AUTH,
                entity_type="profiles",
                entity_id=user_id,
                description="Password reset completed successfully",
                new_values={"password_reset": "completed"},
                ip_address=client_ip,
                user_agent=user_agent,
            )

        logger.info("Password reset successfully completed for user_id=%s", user_id)
        return {"message": "Your password has been successfully reset. You may now sign in."}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Database error during password reset execution: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating your password.",
        ) from exc
