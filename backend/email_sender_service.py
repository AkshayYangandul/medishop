"""Admin-managed sender identities shared by transactional email providers."""
import re
import uuid
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
logger = logging.getLogger("medishop.email_senders")


class BrevoSenderVerificationError(Exception):
    """Sanitized, user-safe failure from Brevo's sender-list endpoint."""

    def __init__(self, detail, status_code=None):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _sanitize_brevo_error(value):
    message = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    for key in ("BREVO_API_KEY", "SMTP_PASSWORD", "SMTP_USER", "SMTP_ENCRYPTION_KEY", "AUTH_SECRET_KEY"):
        secret = os.getenv(key, "").strip()
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:400]


def _provider_error_detail(status_code, body):
    code = ""
    message = ""
    try:
        payload = json.loads(body.decode("utf-8", errors="replace")) if isinstance(body, bytes) else json.loads(str(body))
        if isinstance(payload, dict):
            code = _sanitize_brevo_error(payload.get("code", ""))
            message = _sanitize_brevo_error(payload.get("message", payload.get("error", "")))
    except Exception:
        pass
    detail = f"Brevo sender verification returned HTTP {status_code}"
    if code:
        detail += f" ({code})"
    if message:
        detail += f": {message}"
    if status_code == 403:
        detail += " Check that this API key has permission to read account sender settings for GET /v3/senders."
    elif status_code == 401:
        detail += " Check that BREVO_API_KEY is valid and enabled."
    return detail


def brevo_sender_status(sender_email):
    """Return Brevo's active flag or raise a sanitized error if status is unavailable."""
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key:
        raise BrevoSenderVerificationError("BREVO_API_KEY is not configured; Brevo sender verification cannot be checked.")
    request = urllib.request.Request("https://api.brevo.com/v3/senders",
        headers={"api-key": api_key, "accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = response.status
            body = response.read()
        if not 200 <= status_code < 300:
            raise BrevoSenderVerificationError(_provider_error_detail(status_code, body), status_code)
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise BrevoSenderVerificationError("Brevo returned an unreadable sender-list response.", status_code) from None
        if not isinstance(data, dict) or not isinstance(data.get("senders"), list):
            raise BrevoSenderVerificationError("Brevo returned an unexpected sender-list response.", status_code)
        match = next((item for item in data["senders"] if isinstance(item, dict)
                      and str(item.get("email", "")).lower() == sender_email.lower()), None)
        return bool(match and match.get("active") is True)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        exc.close()
        detail = _provider_error_detail(exc.code, body)
        logger.warning("Brevo GET /v3/senders failed: %s", detail)
        raise BrevoSenderVerificationError(detail, exc.code) from None
    except BrevoSenderVerificationError as exc:
        logger.warning("Brevo GET /v3/senders failed: %s", exc.detail)
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", None)
        detail = "Brevo sender verification could not connect to GET /v3/senders"
        if isinstance(reason, str):
            detail += f" ({_sanitize_brevo_error(reason)})"
        else:
            detail += f" ({type(exc).__name__})"
        logger.warning("Brevo GET /v3/senders failed: %s", detail)
        raise BrevoSenderVerificationError(detail) from None
    except Exception as exc:
        detail = f"Brevo sender verification failed while reading GET /v3/senders ({type(exc).__name__})."
        logger.warning("Brevo GET /v3/senders failed: %s", detail)
        raise BrevoSenderVerificationError(detail) from None


def _email(value, label):
    clean = (value or "").strip()
    if clean and not EMAIL_RE.fullmatch(clean):
        raise HTTPException(422, f"{label} must be a valid email address.")
    return clean


def list_senders(engine):
    with engine.begin() as conn:
        rows = conn.execute(text("""SELECT id, sender_email, sender_name, reply_to_email,
            is_verified, verification_method, verified_at, is_active, disabled_at, created_at
            FROM email_sender_identities ORDER BY created_at DESC""")).mappings().all()
    senders = []
    for row in rows:
        item = dict(row)
        # Older application versions may have stored a manual attestation. Such
        # rows are no longer considered verified or active.
        item["is_verified"] = bool(item["is_verified"] and item.get("verification_method") == "brevo_api")
        item["is_active"] = bool(item["is_active"] and item["is_verified"])
        senders.append(item)
    return senders


def active_sender(engine, required=False):
    try:
        with engine.begin() as conn:
            row = conn.execute(text("""SELECT sender_email AS from_email, sender_name AS from_name,
                reply_to_email, is_verified FROM email_sender_identities
                WHERE is_active=1 AND is_verified=1 AND verification_method='brevo_api'
                AND disabled_at IS NULL LIMIT 1""")).mappings().first()
    except Exception:
        if required:
            raise
        return None
    if not row or not row.get("is_verified"):
        if required:
            raise HTTPException(503, "No active verified sender identity is configured.")
        return None
    return dict(row)


def add_sender(engine, data):
    email = _email(data.get("sender_email"), "Sender email")
    reply = _email(data.get("reply_to_email"), "Reply-To")
    name = (data.get("sender_name") or "").strip()
    if not email or not name:
        raise HTTPException(422, "Sender email and display name are required.")
    sender_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(text("""INSERT INTO email_sender_identities
                (id, sender_email, sender_name, reply_to_email, is_verified, is_active)
                VALUES (:id, :email, :name, :reply, 0, 0)"""),
                {"id": sender_id, "email": email, "name": name, "reply": reply or None})
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(409, "That sender identity already exists.") from exc
        raise
    return {"id": sender_id, "message": "Sender identity added as unverified. Verify it in Brevo before activation."}


def update_sender(engine, sender_id, data):
    email = _email(data.get("sender_email"), "Sender email")
    reply = _email(data.get("reply_to_email"), "Reply-To")
    name = (data.get("sender_name") or "").strip()
    if not email or not name:
        raise HTTPException(422, "Sender email and display name are required.")
    try:
        with engine.begin() as conn:
            prior = conn.execute(text("SELECT sender_email, is_verified FROM email_sender_identities WHERE id=:id FOR UPDATE"), {"id": sender_id}).mappings().first()
            if not prior:
                raise HTTPException(404, "Sender identity was not found.")
            changed_email = prior["sender_email"].lower() != email.lower()
            conn.execute(text("""UPDATE email_sender_identities SET sender_email=:email,
                sender_name=:name, reply_to_email=:reply,
                is_verified=IF(:changed, 0, is_verified),
                verification_method=IF(:changed, NULL, verification_method),
                verified_at=IF(:changed, NULL, verified_at),
                is_active=IF(:changed, 0, is_active) WHERE id=:id"""),
                {"id": sender_id, "email": email, "name": name, "reply": reply or None,
                 "changed": changed_email})
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(409, "That sender identity already exists.") from exc
        raise
    if changed_email:
        return {"message": "Sender updated. The new email address must be verified in Brevo and confirmed again before activation."}
    return {"message": "Sender identity updated."}


def mark_sender_verified(engine, sender_id, confirmed):
    if not confirmed:
        raise HTTPException(422, "Confirm that this sender was verified in Brevo first.")
    verification_issue = None
    with engine.begin() as conn:
        row = conn.execute(text("SELECT sender_email, disabled_at FROM email_sender_identities WHERE id=:id"),
                           {"id": sender_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Sender identity was not found.")
        try:
            brevo_status = brevo_sender_status(row["sender_email"])
        except BrevoSenderVerificationError as exc:
            verification_issue = (503, exc.detail)
            brevo_status = None
        if verification_issue:
            pass
        elif brevo_status is not True:
            if brevo_status is False:
                conn.execute(text("UPDATE email_sender_identities SET is_active=0 WHERE id=:id"), {"id": sender_id})
            verification_issue = (503, "Brevo sender verification could not be checked. Confirm API access and connectivity; the sender remains inactive.") if brevo_status is None else (409, "Brevo does not report this sender as active. Verify or activate it in Brevo first.")
        else:
            conn.execute(text("""UPDATE email_sender_identities SET
                is_active=IF(disabled_at IS NULL, is_active, 0), is_verified=1,
                verification_method='brevo_api', verified_at=:now WHERE id=:id"""),
                {"now": datetime.now(timezone.utc).replace(tzinfo=None), "id": sender_id})
    if verification_issue:
        raise HTTPException(*verification_issue)
    return {"message": "Brevo confirmed this sender as active and verified."}


def activate_sender(engine, sender_id):
    verification_issue = None
    with engine.begin() as conn:
        conn.execute(text("SELECT id FROM email_sender_identities FOR UPDATE"))
        row = conn.execute(text("SELECT is_verified, verification_method, disabled_at FROM email_sender_identities WHERE id=:id FOR UPDATE"), {"id": sender_id}).mappings().first()
        if not row:
            raise HTTPException(404, "Sender identity was not found.")
        if not row["is_verified"] or row["verification_method"] != "brevo_api":
            raise HTTPException(409, "Only a sender verified through the Brevo API can be activated.")
        sender_email = conn.execute(text("SELECT sender_email FROM email_sender_identities WHERE id=:id"), {"id": sender_id}).scalar_one()
        try:
            brevo_status = brevo_sender_status(sender_email)
        except BrevoSenderVerificationError as exc:
            verification_issue = (503, exc.detail)
            brevo_status = None
        if verification_issue:
            pass
        elif brevo_status is False:
            conn.execute(text("UPDATE email_sender_identities SET is_active=0 WHERE id=:id"), {"id": sender_id})
            verification_issue = (409, "Brevo no longer reports this sender as active; verify it in Brevo before activation.")
        else:
            conn.execute(text("UPDATE email_sender_identities SET is_active=0"))
            conn.execute(text("UPDATE email_sender_identities SET is_active=1, disabled_at=NULL WHERE id=:id"), {"id": sender_id})
    if verification_issue:
        raise HTTPException(*verification_issue)
    return {"message": "Active sender identity updated."}


def disable_sender(engine, sender_id):
    with engine.begin() as conn:
        result = conn.execute(text("UPDATE email_sender_identities SET is_active=0, disabled_at=:now WHERE id=:id"),
            {"now": datetime.now(timezone.utc).replace(tzinfo=None), "id": sender_id})
        if not result.rowcount:
            raise HTTPException(404, "Sender identity was not found.")
    return {"message": "Sender identity disabled."}

