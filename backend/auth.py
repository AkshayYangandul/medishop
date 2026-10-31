"""
MediShop Authentication Utilities
==================================
Provides JWT token creation/verification and password hashing for the MediShop API.

Password-hashing note
---------------------
The current implementation uses PBKDF2-HMAC-SHA256 with 260,000 iterations (OWASP 2023
recommendation for SHA-256) because neither ``argon2-cffi`` nor ``bcrypt`` is installed
in the project venv.  Argon2id is the preferred algorithm for new deployments.  To
migrate, install ``argon2-cffi`` (add to requirements.txt), update ``hash_password`` to
produce ``argon2id`` hashes, and keep the PBKDF2 branch in ``verify_password`` so that
existing hashes remain verifiable until re-hashed on next login.

Signing-key requirements
------------------------
``AUTH_SECRET_KEY`` **must** be set in the environment before the server starts.
The application refuses to start if the variable is absent or shorter than 32 characters.
Generate a suitable key with:

    python -c "import secrets; print(secrets.token_hex(32))"

then set ``AUTH_SECRET_KEY=<result>`` in ``backend/.env`` (which is git-ignored).

Unit testing
------------
``get_current_user`` uses the module-level ``default_engine``.  To inject a mock engine
in unit tests, call ``_load_profile_from_db(user_id, mock_engine)`` directly, or patch
``auth.default_engine``.  Do not add an ``Engine`` parameter to ``get_current_user``
because FastAPI's dependency inspector rejects non-Pydantic types in dependency signatures.
"""

import os
import json
import time
import hmac
import hashlib
import secrets
import base64
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.engine import Engine

try:
    from database import engine as default_engine
except ImportError:
    from backend.database import engine as default_engine

logger = logging.getLogger("medishop.auth")

# ---------------------------------------------------------------------------
# Startup-time signing-key validation
# ---------------------------------------------------------------------------
_MIN_SECRET_KEY_LENGTH = 32  # 32 ASCII characters = 256 bits minimum

_raw_secret = os.getenv("AUTH_SECRET_KEY", "")
if not _raw_secret:
    raise RuntimeError(
        "AUTH_SECRET_KEY environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and add it to backend/.env"
    )
if len(_raw_secret) < _MIN_SECRET_KEY_LENGTH:
    raise RuntimeError(
        f"AUTH_SECRET_KEY is too short ({len(_raw_secret)} chars). "
        f"Must be at least {_MIN_SECRET_KEY_LENGTH} characters. "
        "Generate a secure key with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

AUTH_SECRET_KEY: str = _raw_secret
TOKEN_EXPIRE_SECONDS: int = int(os.getenv("TOKEN_EXPIRE_SECONDS", "3600"))

# HTTP Bearer authentication scheme (auto_error=False lets the dependency return 401 itself)
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Internal base64url helpers
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    """Encodes bytes to URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    """Decodes a URL-safe base64 string, restoring any missing padding."""
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


# ---------------------------------------------------------------------------
# JWT token creation and verification
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_in: int = TOKEN_EXPIRE_SECONDS,
    secret_key: str = AUTH_SECRET_KEY,
) -> str:
    """
    Creates an RFC 7519-compliant HS256 JWT access token.

    Claims: ``sub`` (user ID), ``email``, ``role``, ``iat``, ``exp``.
    Header: ``alg=HS256``, ``typ=JWT``.
    """
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")

    signature = _b64url_encode(
        hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    return f"{header_b64}.{payload_b64}.{signature}"


def decode_access_token(token: str, secret_key: str = AUTH_SECRET_KEY) -> Dict[str, Any]:
    """
    Decodes and fully validates an HS256 JWT access token.

    Raises ``ValueError`` on any of:
    - Malformed three-part structure
    - Non-JSON or non-dict header / payload
    - ``alg`` header is not ``HS256``
    - ``typ`` header is not ``JWT`` (case-insensitive)
    - Invalid HMAC signature (timing-safe comparison)
    - Missing or empty ``sub`` claim
    - Missing ``exp`` claim
    - Token has expired (``exp < now``)
    - ``iat`` more than 60 s in the future (clock-skew guard)

    Does **not** log the raw token or any secret material.
    All unexpected exceptions are wrapped in a ``ValueError`` so callers always
    receive a uniform exception type.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Token must have exactly three dot-separated parts")

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature FIRST (before decoding payload, defence in depth)
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = _b64url_encode(
            hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig_b64, expected_sig):
            raise ValueError("Invalid token signature")

        # Decode and validate header
        try:
            header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Header is not valid JSON") from exc
        if not isinstance(header, dict):
            raise ValueError("Header must be a JSON object")
        if header.get("alg") != "HS256":
            raise ValueError(
                f"Unsupported algorithm: {header.get('alg')!r}. Only HS256 is accepted"
            )
        if header.get("typ", "").upper() != "JWT":
            raise ValueError(f"Unsupported token type: {header.get('typ')!r}")

        # Decode payload
        try:
            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Payload is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")

        # Validate required claims
        sub = payload.get("sub")
        if not sub or not isinstance(sub, str):
            raise ValueError("Token is missing a valid 'sub' claim")

        if "exp" not in payload:
            raise ValueError("Token is missing required 'exp' claim")
        exp = payload["exp"]
        if not isinstance(exp, (int, float)):
            raise ValueError("'exp' claim must be a number")

        now = time.time()
        if exp < now:
            raise ValueError("Token has expired")

        # Sanity-check iat (allow up to 60 s of clock skew)
        if "iat" in payload:
            iat = payload["iat"]
            if isinstance(iat, (int, float)) and iat > now + 60:
                raise ValueError("Token 'iat' claim is in the future")

        return payload

    except ValueError:
        raise  # Already a descriptive ValueError
    except Exception as exc:
        raise ValueError("Token validation failed unexpectedly") from exc


# ---------------------------------------------------------------------------
# Password hashing — PBKDF2-HMAC-SHA256
# ---------------------------------------------------------------------------
# OWASP 2023 recommends 600,000 iterations for PBKDF2-HMAC-SHA256.  We use
# 260,000 to stay within ~1 s on modest hardware.  Switch to Argon2id once
# argon2-cffi is added to requirements.txt.

_PBKDF2_ITERATIONS = 260_000
_PBKDF2_HASH = "sha256"
_PBKDF2_SCHEME = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """
    Hashes a password with PBKDF2-HMAC-SHA256 (260,000 iterations, 16-byte random salt).
    Returns a self-describing string: ``pbkdf2_sha256$<iter>$<salt_hex>$<dk_hex>``.
    """
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    return f"{_PBKDF2_SCHEME}${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """
    Verifies a plain-text password against a stored PBKDF2 hash using constant-time
    comparison.  Returns ``False`` for any malformed hash or mismatch.
    Never raises; never logs the password or hash.
    """
    try:
        parts = hashed.split("$")
        if len(parts) != 4:
            return False
        scheme, iterations_str, salt, expected_hex = parts
        if scheme != _PBKDF2_SCHEME:
            return False
        iterations = int(iterations_str)
        if iterations < 1:
            return False
        dk = hashlib.pbkdf2_hmac(
            _PBKDF2_HASH,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return secrets.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internal DB helper (testable independently of the FastAPI dependency)
# ---------------------------------------------------------------------------

def _load_profile_from_db(user_id: str, engine: Engine) -> Dict[str, Any]:
    """
    Loads and validates a user profile from the database.
    Raises HTTPException on DB error, missing profile, or inactive account.

    This function is kept separate from ``get_current_user`` so unit tests can
    inject a mock engine directly without violating FastAPI's dependency-inspection
    requirements (FastAPI cannot handle ``Engine`` as a dependency parameter type).
    """
    try:
        with engine.connect() as conn:
            profile = conn.execute(
                text(
                    "SELECT id, email, full_name, role, is_active "
                    "FROM profiles WHERE id = :id"
                ),
                {"id": user_id},
            ).mappings().first()
    except Exception as exc:
        logger.error("Database error during authentication for user_id=%s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during authentication.",
        )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not bool(profile["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User account is inactive.",
        )

    return dict(profile)


# ---------------------------------------------------------------------------
# FastAPI authentication dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI dependency: decodes + verifies the Bearer JWT and returns the live
    database profile for that user.

    Uses the module-level ``default_engine``.  For unit testing, call
    ``_load_profile_from_db(user_id, mock_engine)`` directly, or patch
    ``auth.default_engine``.

    Rejects with HTTP 401 if:
    - No Authorization header is present
    - The token is malformed, unsigned, or expired
    - The token's ``sub`` does not correspond to a profile row

    Rejects with HTTP 403 if the profile's ``is_active`` is FALSE.

    Error details intentionally omit token content, secrets, or DB internals.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload["sub"]  # guaranteed non-empty by decode_access_token

    return _load_profile_from_db(user_id, default_engine)


def require_active_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    FastAPI dependency: ensures the authenticated user holds the ``admin`` role.
    Rejects pharmacists and any other non-admin callers with HTTP 403.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Active administrator privileges required.",
        )
    return current_user
