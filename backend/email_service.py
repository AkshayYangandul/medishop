"""
MediShop Email Delivery Service
=================================
Handles Brevo API dispatch for transactional security notifications such as
password reset emails, account lockout alerts, and failed-login warning notices.

Security Note:
Raw reset tokens and API keys are never logged. Email addresses are sanitized
in logs to protect user privacy.
"""

import html
import os
import logging
import json
import re
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from fastapi import HTTPException
from typing import Optional, Dict, Any

from sqlalchemy.engine import Engine

try:
    from database import engine as default_engine
    from email_sender_service import active_sender
except ImportError:
    from backend.database import engine as default_engine
    from backend.email_sender_service import active_sender

logger = logging.getLogger("medishop.email")
EMAIL_ADDRESS_RE = re.compile(r"^[^\s@]+@[^@\s]+\.[^@\s]+$")


def _sanitize_email_for_log(email: str) -> str:
    """Masks local part of email for safe logging (e.g. j***n@domain.com)."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _get_active_config(engine: Optional[Engine] = None) -> Dict[str, Any]:
    """Fetch the latest active Brevo sender identity from MySQL for this send."""
    target_engine = engine if engine is not None else default_engine
    sender = active_sender(target_engine, required=False)
    return {
        "provider": "brevo", "from_email": (sender or {}).get("from_email", ""),
        "from_name": (sender or {}).get("from_name", ""),
        "reply_to_email": (sender or {}).get("reply_to_email"),
    }


def dispatch_transactional_message(msg, to_email, engine=None, log_description="Transactional email",
                                   raise_on_failure=False, config_override=None):
    """Shared Brevo-only dispatcher used by every transactional email workflow."""
    cfg = config_override if config_override is not None else _get_active_config(engine)
    return _dispatch_brevo_message(msg, to_email, cfg, log_description, raise_on_failure)


def _dispatch_brevo_message(msg, to_email, cfg, log_description, raise_on_failure=False) -> bool:
    """Submit MIME content through Brevo's Transactional Email API (never fallback)."""
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    if not api_key:
        logger.error("Brevo delivery unavailable for %s: BREVO_API_KEY is not configured", log_description)
        if raise_on_failure:
            raise RuntimeError("Brevo is selected but BREVO_API_KEY is not configured.")
        return False
    if not cfg.get("from_email"):
        logger.error("Brevo delivery unavailable for %s: no active verified sender is configured", log_description)
        if raise_on_failure:
            raise RuntimeError("No active verified sender identity is configured for Brevo.")
        return False
    text_body, html_body = "", ""
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        try:
            body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:
            body = str(part.get_payload())
        if part.get_content_subtype() == "html":
            html_body = body
        elif part.get_content_subtype() == "plain":
            text_body = body
    payload = {"sender": {"email": cfg["from_email"], "name": cfg.get("from_name") or "MediShop"},
               "to": [{"email": to_email}], "subject": str(msg.get("Subject", "")),
               "textContent": text_body, "htmlContent": html_body}
    if cfg.get("reply_to_email"):
        payload["replyTo"] = {"email": cfg["reply_to_email"]}
    request = urllib.request.Request("https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": api_key, "accept": "application/json", "content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                logger.error("Brevo rejected %s with HTTP %s", log_description, response.status)
                return False
        logger.info("Brevo accepted %s for %s; acceptance does not confirm inbox delivery",
                    log_description, _sanitize_email_for_log(to_email))
        return True
    except urllib.error.HTTPError as exc:
        request_id = exc.headers.get("x-sib-request-id", "") if exc.headers else ""
        exc.close()
        logger.error("Brevo rejected %s with HTTP %s (request id %s)", log_description, exc.code, request_id[:80])
        if raise_on_failure:
            raise RuntimeError(f"Brevo rejected the request (HTTP {exc.code}). Check the API key, sender authorization, and message configuration.") from None
    except (TimeoutError, urllib.error.URLError, OSError) as exc:
        logger.error("Brevo delivery failed for %s (%s)", log_description, type(exc).__name__)
        if raise_on_failure:
            raise RuntimeError(f"Could not connect to Brevo ({type(exc).__name__}).") from None
    except Exception as exc:
        logger.error("Brevo delivery failed for %s (%s)", log_description, type(exc).__name__)
        if raise_on_failure:
            raise RuntimeError(f"Brevo delivery failed ({type(exc).__name__}).") from None
    return False


def send_test_email(to_email: str, engine: Optional[Engine] = None) -> Dict[str, str]:
    """Send a test message through the shared Brevo dispatcher and active sender."""
    recipient = (to_email or "").strip()
    if not EMAIL_ADDRESS_RE.fullmatch(recipient):
        raise HTTPException(422, "A valid recipient email address is required for test email delivery.")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "MediShop: Transactional Email Test"
    msg["To"] = recipient
    msg.attach(MIMEText(
        "Brevo accepted this MediShop test message request. Acceptance does not confirm inbox delivery.",
        "plain", "utf-8"))
    msg.attach(MIMEText(
        "<p>Brevo accepted this MediShop test message request.</p><p>Acceptance does not confirm inbox delivery.</p>",
        "html", "utf-8"))
    try:
        accepted = dispatch_transactional_message(
            msg, recipient, engine=engine, log_description="Admin test email", raise_on_failure=True)
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from None
    if not accepted:
        raise HTTPException(422, "Brevo did not accept the test email request.")
    return {"status": "accepted", "message": f"Brevo accepted the test email request for {recipient}; inbox delivery is not confirmed."}


def send_password_reset_email(
    to_email: str,
    reset_token: str,
    recipient_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> bool:
    """
    Constructs and sends a password reset email containing a single-use link.
    Returns True if successfully dispatched, False if unconfigured or failed.
    """
    cfg = _get_active_config(engine)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    from_email = cfg["from_email"]
    from_name = cfg["from_name"]
    reply_to = cfg.get("reply_to_email")

    reset_url = f"{frontend_url}/reset-password?token={reset_token}"
    raw_name = recipient_name.strip() if recipient_name else "Staff Member"
    display_name = html.escape(raw_name, quote=False)
    display_name_text = raw_name

    text_content = (
        f"Hello {display_name_text},\n\n"
        f"We received a request to reset the password for your MediShop account.\n\n"
        f"Please click the link below to choose a new password (valid for 30 minutes):\n"
        f"{reset_url}\n\n"
        f"If you did not request this change, you can safely ignore this email; your "
        f"existing password will remain unchanged.\n\n"
        f"Best regards,\n"
        f"The MediShop Security Team\n"
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Reset Your MediShop Password</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
    .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
    .header {{ text-align: center; margin-bottom: 24px; }}
    .brand {{ font-size: 22px; font-weight: 800; color: #0284c7; letter-spacing: -0.5px; }}
    .btn {{ display: inline-block; background-color: #0284c7; color: #ffffff !important; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 14px; margin: 20px 0; }}
    .footer {{ font-size: 12px; color: #64748b; margin-top: 28px; border-top: 1px solid #f1f5f9; padding-top: 16px; line-height: 1.5; }}
    .link-alt {{ word-break: break-all; color: #0284c7; font-size: 12px; }}
    .badge {{ display: inline-block; background: #fef3c7; color: #92400e; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">MediShop Pharmacy Suite</div>
      <div style="font-size: 13px; color: #64748b; margin-top: 4px;">Security &amp; Account Protection</div>
    </div>
    
    <p style="font-size: 15px; font-weight: 600;">Hello {display_name},</p>
    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
      We received a request to reset your password for MediShop. Click the button below to establish a new password for your account:
    </p>

    <div style="text-align: center;">
      <a href="{reset_url}" class="btn" target="_blank">Reset Password</a>
    </div>

    <p style="font-size: 12px; color: #64748b; text-align: center;">
      <span class="badge">Valid for 30 minutes</span> &bull; Single-use link
    </p>

    <div class="footer">
      <p>If the button above does not work, copy and paste this link into your browser:</p>
      <p><a href="{reset_url}" class="link-alt">{reset_url}</a></p>
      <p>If you did not request this password reset, no action is needed; your account credentials remain secure.</p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Reset Your MediShop Password"
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    return dispatch_transactional_message(
        msg, to_email, engine=engine, log_description="Password reset email", config_override=cfg
    )


def send_account_locked_email(
    to_email: str,
    recipient_name: Optional[str] = None,
    engine: Optional[Engine] = None,
) -> bool:
    """
    Constructs and sends a security alert email when an account is locked
    after five consecutive failed login attempts.
    """
    cfg = _get_active_config(engine)
    from_email = cfg["from_email"]
    from_name = cfg["from_name"]
    reply_to = cfg.get("reply_to_email")

    raw_name = recipient_name.strip() if recipient_name else "Staff Member"
    display_name = html.escape(raw_name, quote=False)

    text_content = (
        f"Hello {raw_name},\n\n"
        f"Your MediShop account has been locked after five consecutive failed "
        f"login attempts.\n\n"
        f"If this was not you, contact your MediShop administrator to request "
        f"an unlock. Do not share your password with anyone.\n\n"
        f"Best regards,\n"
        f"The MediShop Security Team\n"
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>MediShop Account Locked</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
    .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
    .header {{ text-align: center; margin-bottom: 24px; }}
    .brand {{ font-size: 22px; font-weight: 800; color: #0284c7; letter-spacing: -0.5px; }}
    .footer {{ font-size: 12px; color: #64748b; margin-top: 28px; border-top: 1px solid #f1f5f9; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">MediShop Pharmacy Suite</div>
      <div style="font-size: 13px; color: #64748b; margin-top: 4px;">Security &amp; Account Protection</div>
    </div>

    <p style="font-size: 15px; font-weight: 600;">Hello {display_name},</p>
    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
      Your MediShop account has been locked after five consecutive failed login attempts.
    </p>
    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
      If this was not you, contact your MediShop administrator to request an unlock.
      Do not share your password with anyone.
    </p>

    <div class="footer">
      <p>The MediShop Security Team</p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Security Alert: MediShop Account Locked"
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    return dispatch_transactional_message(
        msg, to_email, engine=engine, log_description="Account lockout alert", config_override=cfg
    )


def send_login_warning_email(
    to_email: str,
    recipient_name: Optional[str] = None,
    failed_attempts: int = 3,
    remaining_attempts: int = 2,
    engine: Optional[Engine] = None,
) -> bool:
    """
    Constructs and sends a security warning email after the third consecutive
    failed login attempt.
    """
    cfg = _get_active_config(engine)
    from_email = cfg["from_email"]
    from_name = cfg["from_name"]
    reply_to = cfg.get("reply_to_email")

    raw_name = recipient_name.strip() if recipient_name else "Staff Member"
    display_name = html.escape(raw_name, quote=False)

    text_content = (
        f"Hello {raw_name},\n\n"
        f"There have been {failed_attempts} unsuccessful login attempts on your "
        f"MediShop account.\n\n"
        f"Warning: {remaining_attempts} more incorrect attempts will temporarily "
        f"lock your account.\n\n"
        f"If this was not you, contact your MediShop administrator. Do not share "
        f"your password with anyone.\n\n"
        f"Best regards,\n"
        f"The MediShop Security Team\n"
    )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>MediShop Login Security Warning</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b; }}
    .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }}
    .header {{ text-align: center; margin-bottom: 24px; }}
    .brand {{ font-size: 22px; font-weight: 800; color: #0284c7; letter-spacing: -0.5px; }}
    .badge {{ display: inline-block; background: #fef3c7; color: #92400e; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 4px; }}
    .footer {{ font-size: 12px; color: #64748b; margin-top: 28px; border-top: 1px solid #f1f5f9; padding-top: 16px; line-height: 1.5; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">MediShop Pharmacy Suite</div>
      <div style="font-size: 13px; color: #64748b; margin-top: 4px;">Security &amp; Account Protection</div>
    </div>

    <p style="font-size: 15px; font-weight: 600;">Hello {display_name},</p>
    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
      There have been <strong>{failed_attempts} unsuccessful login attempts</strong>
      on your MediShop account.
    </p>
    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
      <span class="badge">Warning</span>
      <strong>{remaining_attempts} more incorrect attempts</strong> will temporarily
      lock your account.
    </p>
    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
      If this was not you, contact your MediShop administrator. Do not share your
      password with anyone.
    </p>

    <div class="footer">
      <p>The MediShop Security Team</p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Security Warning: Unsuccessful MediShop Login Attempts"
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    return dispatch_transactional_message(
        msg, to_email, engine=engine,
        log_description=f"Login security warning ({failed_attempts} failed attempts)",
        config_override=cfg,
    )
