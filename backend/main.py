import logging
import os
from typing import Optional, Dict, Any, List
from datetime import date
from decimal import Decimal
from fastapi import FastAPI, Response, Request, Depends, status, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

try:
    import audit_service
except ImportError:  # Allow imports from the repository root as well
    import backend.audit_service as audit_service

try:
    import email_sender_service
except ImportError:
    import backend.email_sender_service as email_sender_service

logger = logging.getLogger("medishop.main")

try:
    from database import engine, test_connection
    from user_service import update_user_role_or_status, user_list, user_create
    from auth import get_current_user, require_active_admin, create_access_token, verify_password
    from medicine_service import (
        medicine_brand_create,
        medicine_brand_delete,
        medicine_brand_update,
        medicine_batch_create,
        medicine_batch_list,
        medicine_category_create,
        medicine_category_delete,
        medicine_category_update,
        medicine_create,
        medicine_get,
        medicine_inventory,
        medicine_inventory_list,
        medicine_list,
        medicine_update,
        medicine_brands,
        medicine_categories,
    )
    from sales_service import (
        supplier_list,
        supplier_get,
        supplier_create,
        supplier_update,
        supplier_delete,
        customer_list,
        customer_get,
        customer_create,
        customer_update,
        customer_delete,
        invoice_list,
        invoice_get,
        invoice_create,
        purchase_list,
        purchase_get,
        purchase_create,
        expense_list,
        expense_create,
        expense_delete,
        dashboard_stats,
        reports_summary,
    )
    from auth_reset_service import (
        request_password_reset,
        verify_reset_token,
        execute_password_reset,
    )
    from email_service import send_account_locked_email, send_login_warning_email, send_test_email
    from user_service import (
        update_user_role_or_status,
        user_list,
        user_create,
        unlock_user_account,
        delete_user_account,
        restore_user_account,
    )
except ImportError:
    from backend.database import engine, test_connection
    from backend.user_service import (
        update_user_role_or_status,
        user_list,
        user_create,
        unlock_user_account,
        delete_user_account,
        restore_user_account,
    )
    from backend.auth import get_current_user, require_active_admin, create_access_token, verify_password
    from backend.auth_reset_service import (
        request_password_reset,
        verify_reset_token,
        execute_password_reset,
    )
    from backend.email_service import send_account_locked_email, send_login_warning_email, send_test_email
    from backend.medicine_service import (
        medicine_brand_create,
        medicine_brand_delete,
        medicine_brand_update,
        medicine_batch_create,
        medicine_batch_list,
        medicine_category_create,
        medicine_category_delete,
        medicine_category_update,
        medicine_create,
        medicine_get,
        medicine_inventory,
        medicine_inventory_list,
        medicine_list,
        medicine_update,
        medicine_brands,
        medicine_categories,
    )
    from backend.sales_service import (
        supplier_list,
        supplier_get,
        supplier_create,
        supplier_update,
        supplier_delete,
        customer_list,
        customer_get,
        customer_create,
        customer_update,
        customer_delete,
        invoice_list,
        invoice_get,
        invoice_create,
        purchase_list,
        purchase_get,
        purchase_create,
        expense_list,
        expense_create,
        expense_delete,
        dashboard_stats,
        reports_summary,
    )

# Initialize FastAPI application
app = FastAPI(
    title="MediShop API",
    description="Backend API for MediShop Medical Shop Management System",
    version="0.1.0",
)

# Configure CORS for local Vite frontend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request schemas for authentication and user role/status administration
class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="Registered staff email address")


class VerifyResetTokenRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Password reset token")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=6, max_length=100, description="New user password")


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., description="Target role: 'admin' or 'pharmacist'")


class StatusUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="Target active status (True / False)")


class UserRoleStatusUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, description="Target role: 'admin' or 'pharmacist'")
    is_active: Optional[bool] = Field(None, description="Target active status")


class MedicineCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Medicine name")
    generic_name: Optional[str] = Field(None, max_length=255, description="Generic drug name")
    category_id: str = Field(..., min_length=1, max_length=64, description="Category ID (FK)")
    brand_id: Optional[str] = Field(None, max_length=64, description="Brand ID (FK, optional)")
    dosage_form: str = Field(..., description="Dosage form: 'Tablet', 'Capsule', 'Syrup', 'Injection', 'Ointment', 'Drops', 'Inhaler', 'Other'")
    strength: Optional[str] = Field(None, max_length=100, description="Strength / dosage strength")
    unit: str = Field("Strip", max_length=50, description="Stock unit, default 'Strip'")
    hsn_code: Optional[str] = Field(None, max_length=50, description="HSN code")
    requires_prescription: bool = Field(False, description="Whether prescription is required")
    min_stock_alert: int = Field(10, ge=0, description="Low-stock alert threshold")


class MedicineUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Medicine name")
    generic_name: Optional[str] = Field(None, max_length=255, description="Generic drug name")
    category_id: Optional[str] = Field(None, min_length=1, max_length=64, description="Category ID (FK)")
    brand_id: Optional[str] = Field(None, max_length=64, description="Brand ID (FK, optional)")
    dosage_form: Optional[str] = Field(None, max_length=100, description="Dosage form")
    strength: Optional[str] = Field(None, max_length=100, description="Strength / dosage strength")
    unit: Optional[str] = Field(None, max_length=50, description="Stock unit")
    hsn_code: Optional[str] = Field(None, max_length=50, description="HSN code")
    requires_prescription: Optional[bool] = Field(None, description="Whether prescription is required")
    min_stock_alert: Optional[int] = Field(None, ge=0, description="Low-stock alert threshold")
    is_active: Optional[bool] = Field(None, description="Active status (enables deactivation)")


class BatchCreateRequest(BaseModel):
    medicine_id: str = Field(..., min_length=1, max_length=64, description="Medicine ID (FK)")
    batch_no: str = Field(..., min_length=1, max_length=100, description="Batch number")
    mfg_date: Optional[date] = Field(None, description="Manufacture date (optional)")
    expiry_date: date = Field(..., description="Expiry date (required)")
    purchase_cost: Decimal = Field(..., ge=Decimal("0"), description="Purchase cost (non-negative)")
    mrp: Decimal = Field(..., ge=Decimal("0"), description="Maximum retail price (non-negative)")
    selling_price: Decimal = Field(..., ge=Decimal("0"), description="Selling price (non-negative)")
    initial_quantity: int = Field(..., ge=0, description="Received quantity (non-negative)")
    supplier_id: Optional[str] = Field(None, max_length=64, description="Supplier ID (optional)")


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Category name")
    slug: Optional[str] = Field(None, max_length=255, description="Category slug (auto-generated from name when omitted)")
    description: Optional[str] = Field(None, max_length=1000, description="Category description")
    storage_temperature: Optional[str] = Field(None, max_length=100, description="Storage temperature")


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Category name")
    slug: Optional[str] = Field(None, max_length=255, description="Category slug")
    description: Optional[str] = Field(None, max_length=1000, description="Category description")
    storage_temperature: Optional[str] = Field(None, max_length=100, description="Storage temperature")


class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Brand name")
    manufacturer: Optional[str] = Field(None, max_length=255, description="Manufacturer")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")


class BrandUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Brand name")
    manufacturer: Optional[str] = Field(None, max_length=255, description="Manufacturer")
    contact_email: Optional[str] = Field(None, max_length=255, description="Contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone")


class SupplierCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_person: Optional[str] = Field(None, max_length=255)
    phone: str = Field(..., min_length=1, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    gstin: Optional[str] = Field(None, max_length=50)
    drug_license_no: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = True


class SupplierUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_person: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    gstin: Optional[str] = Field(None, max_length=50)
    drug_license_no: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class CustomerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    doctor_name: Optional[str] = Field(None, max_length=255)
    allergies_or_notes: Optional[str] = None


class CustomerUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    doctor_name: Optional[str] = Field(None, max_length=255)
    allergies_or_notes: Optional[str] = None


class InvoiceItemRequest(BaseModel):
    medicine_id: str = Field(..., min_length=1)
    batch_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: Optional[Decimal] = Field(None, ge=Decimal("0"))
    tax_rate: Optional[Decimal] = Field(Decimal("0"), ge=Decimal("0"))
    discount_amount: Optional[Decimal] = Field(Decimal("0"), ge=Decimal("0"))


class InvoiceCreateRequest(BaseModel):
    customer_id: Optional[str] = None
    payment_method: Optional[str] = "cash"
    payment_status: Optional[str] = "paid"
    discount_amount: Optional[Decimal] = Field(Decimal("0"), ge=Decimal("0"))
    doctor_prescription_ref: Optional[str] = None
    notes: Optional[str] = None
    items: List[InvoiceItemRequest] = Field(..., min_length=1)


class PurchaseItemRequest(BaseModel):
    medicine_id: str = Field(..., min_length=1)
    batch_no: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_cost: Decimal = Field(..., ge=Decimal("0"))
    mrp: Optional[Decimal] = Field(None, ge=Decimal("0"))
    selling_price: Optional[Decimal] = Field(None, ge=Decimal("0"))
    expiry_date: date
    mfg_date: Optional[date] = None
    tax_rate: Optional[Decimal] = Field(Decimal("0"), ge=Decimal("0"))


class PurchaseCreateRequest(BaseModel):
    supplier_id: str = Field(..., min_length=1)
    invoice_no: Optional[str] = None
    purchase_date: Optional[date] = None
    payment_status: Optional[str] = "paid"
    discount_amount: Optional[Decimal] = Field(Decimal("0"), ge=Decimal("0"))
    notes: Optional[str] = None
    items: List[PurchaseItemRequest] = Field(..., min_length=1)


class ExpenseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=Decimal("0"))
    expense_date: Optional[date] = None
    payment_method: Optional[str] = "cash"
    receipt_url: Optional[str] = None
    notes: Optional[str] = None


class UserCreateRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field("pharmacist", min_length=1, max_length=50, description="Target role: 'admin' or 'pharmacist'")
    phone: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = True


class UserRestoreRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class ProviderTestEmailRequest(BaseModel):
    recipient_email: str = Field(..., min_length=3, max_length=255,
                                 pattern=r"^[^\s@]+@[^@\s]+\.[^@\s]+$")


class EmailSenderCreateRequest(BaseModel):
    sender_email: str = Field(..., min_length=3, max_length=255)
    sender_name: str = Field(..., min_length=1, max_length=255)
    reply_to_email: Optional[str] = Field(None, max_length=255)


class EmailSenderVerifyRequest(BaseModel):
    confirm_brevo_verified: bool = False


# ==============================================================================
# BASE SYSTEM & HEALTH ENDPOINTS
# ==============================================================================

@app.get("/")
def read_root():
    """Root endpoint to identify the MediShop API."""
    return {
        "name": "MediShop API",
        "version": "0.1.0",
        "message": "Welcome to the MediShop API",
    }


@app.get("/health")
def health_check():
    """Health check endpoint to verify that the API is running."""
    return {
        "status": "healthy",
        "service": "MediShop API",
    }


@app.get("/db-health")
def db_health_check(response: Response):
    """
    Checks the connection from FastAPI to the MySQL database.
    Returns HTTP 200 if connected successfully, or HTTP 503 if the database is unreachable.
    """
    is_connected, error_message = test_connection()

    if is_connected:
        return {
            "status": "connected",
            "database": "MySQL",
            "message": "Successfully connected to the MediShop MySQL database.",
        }

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "error",
        "database": "MySQL",
        "message": "Could not connect to the MySQL database.",
    }


# ==============================================================================
# AUTHENTICATION ENDPOINT
# Verifies credentials against profiles and issues cryptographically signed JWT
# ==============================================================================

# Number of consecutive failed password attempts that lock an account.
FAILED_LOGIN_ATTEMPT_THRESHOLD = 5

# Number of consecutive failed password attempts that trigger the one-time
# security warning email (the account is NOT locked at this stage).
LOGIN_WARNING_ATTEMPT_THRESHOLD = 3


def _request_meta(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    """Returns (client_ip, user_agent) without trusting forwarded headers."""
    if request is None:
        return None, None
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return client_ip, user_agent


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request = None):
    """
    Authenticates an active user against the database and returns a signed Bearer token.

    Failed-login security (row-locked, single database transaction):
    - A missing profile or an incorrect password yields a generic HTTP 401 so the
      requester cannot distinguish "unknown email" from "wrong password".
    - For a known account with a wrong password the failed-attempt counter is
      incremented atomically inside the same transaction that holds a ``FOR UPDATE``
      row lock, so concurrent requests cannot bypass the fifth-attempt threshold.
    - On the fifth consecutive failure the account is locked (``account_locked``,
      ``locked_at``) and exactly one security alert email is dispatched after the
      transaction commits. The response stays generic.
    - An already locked account is rejected before any session or token is created,
      even when the password is correct, and no further counter increments or
      emails are generated.
    - A successful login resets the failed-attempt counter to zero.
    """
    profile: Dict[str, Any] | None = None
    newly_locked = False
    locked_out_email: str | None = None
    locked_out_name: str | None = None
    warning_email: str | None = None
    warning_name: str | None = None
    failure_error: HTTPException | None = None
    audit_events: List[Dict[str, Any]] = []
    client_ip, user_agent = _request_meta(request)

    try:
        # One transaction, one row lock held for the whole check/update cycle.
        # ``engine.connect()`` plus an explicit ``conn.begin()``/``trans.commit()``
        # mirrors the transaction pattern already used by ``user_service.py`` and
        # keeps the existing login unit-test mocks (which stub ``engine.connect``)
        # working unchanged.
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                row = conn.execute(
                    text(
                        "SELECT id, email, password_hash, full_name, role, is_active, "
                        "failed_login_attempts, account_locked, locked_at "
                        "FROM profiles WHERE email = :email AND deleted_at IS NULL FOR UPDATE"
                    ),
                    {"email": payload.email},
                ).mappings().first()

                if row is None:
                    # Unknown email: no row to lock, no counter to increment.
                    audit_events.append({
                        "actor": None,
                        "action": audit_service.ACTION_LOGIN_FAILED,
                        "module": audit_service.MODULE_AUTH,
                        "entity_type": "profiles",
                        "entity_id": None,
                        "description": "Failed login attempt for unknown email",
                        "new_values": {"reason": "unknown_email"},
                    })
                    failure_error = HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                elif bool(row.get("account_locked", False)):
                    # Already locked: reject before any session/token, no re-email,
                    # no re-count.
                    audit_events.append({
                        "actor": {
                            "id": row["id"],
                            "full_name": row.get("full_name"),
                            "role": row.get("role"),
                        },
                        "action": audit_service.ACTION_LOGIN_FAILED,
                        "module": audit_service.MODULE_AUTH,
                        "entity_type": "profiles",
                        "entity_id": row["id"],
                        "description": "Login attempt on a locked account",
                        "new_values": {"reason": "account_locked"},
                    })
                    failure_error = HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=(
                            "Account is locked due to multiple failed login "
                            "attempts. Please contact your MediShop administrator "
                            "to request an unlock."
                        ),
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                elif not verify_password(payload.password, row["password_hash"]):
                    # Incorrect password: increment the counter under the row lock.
                    new_count = int(row.get("failed_login_attempts", 0) or 0) + 1
                    newly_locked = new_count >= FAILED_LOGIN_ATTEMPT_THRESHOLD
                    actor_snapshot = {
                        "id": row["id"],
                        "full_name": row.get("full_name"),
                        "role": row.get("role"),
                    }
                    if newly_locked:
                        conn.execute(
                            text(
                                "UPDATE profiles "
                                "SET failed_login_attempts = :count, "
                                "account_locked = TRUE, locked_at = NOW() "
                                "WHERE id = :id"
                            ),
                            {"count": new_count, "id": row["id"]},
                        )
                        locked_out_email = row["email"]
                        locked_out_name = row.get("full_name")
                    else:
                        conn.execute(
                            text(
                                "UPDATE profiles "
                                "SET failed_login_attempts = :count WHERE id = :id"
                            ),
                            {"count": new_count, "id": row["id"]},
                        )
                        # One-time warning on exactly the third consecutive
                        # failure.  Attempts 1-2 do nothing; attempts 4-5 do not
                        # re-send because ``new_count`` only equals the warning
                        # threshold once per consecutive-failure sequence.
                        if new_count == LOGIN_WARNING_ATTEMPT_THRESHOLD:
                            warning_email = row["email"]
                            warning_name = row.get("full_name")
                    audit_events.append({
                        "actor": actor_snapshot,
                        "action": audit_service.ACTION_LOGIN_FAILED,
                        "module": audit_service.MODULE_AUTH,
                        "entity_type": "profiles",
                        "entity_id": row["id"],
                        "description": (
                            f"Failed login attempt ({new_count} of "
                            f"{FAILED_LOGIN_ATTEMPT_THRESHOLD})"
                        ),
                        "old_values": {
                            "failed_login_attempts": int(row.get("failed_login_attempts", 0) or 0),
                            "account_locked": False,
                        },
                        "new_values": {
                            "failed_login_attempts": new_count,
                            "account_locked": newly_locked,
                        },
                    })
                    if newly_locked:
                        audit_events.append({
                            "actor": actor_snapshot,
                            "action": audit_service.ACTION_ACCOUNT_LOCKED,
                            "module": audit_service.MODULE_AUTH,
                            "entity_type": "profiles",
                            "entity_id": row["id"],
                            "description": (
                                "Account locked after repeated failed login attempts"
                            ),
                            "old_values": {"account_locked": False},
                            "new_values": {
                                "account_locked": True,
                                "failed_login_attempts": new_count,
                            },
                        })
                    failure_error = HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                else:
                    # Correct password: reset the counter, keep everything else
                    # unchanged.
                    if int(row.get("failed_login_attempts", 0) or 0) > 0:
                        conn.execute(
                            text("UPDATE profiles SET failed_login_attempts = 0 "
                                 "WHERE id = :id"),
                            {"id": row["id"]},
                        )
                    profile = dict(row)
                    is_active_profile = bool(row.get("is_active", False))
                    audit_events.append({
                        "actor": {
                            "id": row["id"],
                            "full_name": row.get("full_name"),
                            "role": row.get("role"),
                        },
                        "action": (
                            audit_service.ACTION_LOGIN_SUCCESS
                            if is_active_profile
                            else audit_service.ACTION_LOGIN_FAILED
                        ),
                        "module": audit_service.MODULE_AUTH,
                        "entity_type": "profiles",
                        "entity_id": row["id"],
                        "description": (
                            "Successful login"
                            if is_active_profile
                            else "Login rejected for inactive account"
                        ),
                        "new_values": {
                            "role": row.get("role"),
                            "is_active": is_active_profile,
                        },
                    })

                for event in audit_events:
                    audit_service.record_audit(
                        conn,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        **event,
                    )

                trans.commit()
            except Exception:
                if trans.is_active:
                    trans.rollback()
                raise

    except HTTPException:
        # A generic failure was already decided above; do not mask it as a 500.
        raise
    except Exception as exc:
        logger.error("Database error during login for email=%s: %s",
                     payload.email, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred during login."
        )

    if failure_error is not None:
        # The counter/lock state (if any) was committed above.  Send the
        # one-off notifications outside the transaction so an email failure never
        # undoes the security state change.  Both recipients come exclusively
        # from the authenticated account's database row.
        if warning_email:
            _dispatch_login_warning(
                warning_email,
                warning_name,
                failed_attempts=LOGIN_WARNING_ATTEMPT_THRESHOLD,
                remaining_attempts=(
                    FAILED_LOGIN_ATTEMPT_THRESHOLD - LOGIN_WARNING_ATTEMPT_THRESHOLD
                ),
            )
        if newly_locked and locked_out_email:
            _dispatch_lockout_alert(locked_out_email, locked_out_name)
        raise failure_error

    if profile is None:
        # Defensive: should not be reachable, but never issue a token without a profile.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during login."
        )

    if not bool(profile["is_active"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Account is inactive."
        )

    token = create_access_token(
        user_id=profile["id"],
        email=profile["email"],
        role=profile["role"]
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": profile["id"],
            "email": profile["email"],
            "role": profile["role"]
        }
    }


def _dispatch_login_warning(
    to_email: str,
    recipient_name: str | None,
    failed_attempts: int = LOGIN_WARNING_ATTEMPT_THRESHOLD,
    remaining_attempts: int = (
        FAILED_LOGIN_ATTEMPT_THRESHOLD - LOGIN_WARNING_ATTEMPT_THRESHOLD
    ),
) -> None:
    """
    Best-effort dispatch of the third-attempt login security warning.

    Runs after the database transaction commits.  The recipient is always the
    affected account's registered database email.  A delivery failure is logged
    server-side only and never changes the login response or account state.
    """
    safe_recipient = _sanitize_email(to_email)
    try:
        delivered = send_login_warning_email(
            to_email=to_email,
            recipient_name=recipient_name,
            failed_attempts=failed_attempts,
            remaining_attempts=remaining_attempts,
        )
    except Exception as exc:  # pragma: no cover - defensive; service handles provider errors
        logger.error(
            "Unexpected error while dispatching login security warning to %s: %s",
            safe_recipient,
            type(exc).__name__,
        )
        return

    if delivered:
        logger.info(
            "Login security warning dispatched to %s (failed_attempts=%d)",
            safe_recipient,
            failed_attempts,
        )
    else:
        logger.error(
            "Login security warning NOT delivered to %s (failed_attempts=%d); "
            "check Brevo configuration and server logs.",
            safe_recipient,
            failed_attempts,
        )


def _dispatch_lockout_alert(to_email: str, recipient_name: str | None) -> None:
    """
    Best-effort dispatch of the account-lockout security alert.

    Runs after the database transaction commits. A delivery failure is logged
    server-side only — the lockout stands regardless of email delivery, and the
    caller is never told whether an email was sent.  The recipient is always the
    affected account's registered database email.
    """
    safe_recipient = _sanitize_email(to_email)
    try:
        delivered = send_account_locked_email(
            to_email=to_email, recipient_name=recipient_name
        )
    except Exception as exc:  # pragma: no cover - defensive; email service handles provider errors
        logger.error(
            "Unexpected error while dispatching account lockout alert to %s: %s",
            safe_recipient,
            type(exc).__name__,
        )
        return

    if delivered:
        logger.info("Account lockout alert dispatched to %s", safe_recipient)
    else:
        logger.error(
            "Account lockout alert NOT delivered to %s; "
            "check Brevo configuration and server logs.",
            safe_recipient,
        )


def _sanitize_email(email: str | None) -> str:
    """Mask the local part of an email address for safe logging."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    masked_local = local[0] + "*" * max(0, len(local) - 2) + local[-1] if len(local) > 1 else local
    return f"{masked_local}@{domain}"


# ==============================================================================
# PASSWORD RESET ENDPOINTS
# Public self-service authentication endpoints with anti-enumeration protection
# ==============================================================================

@app.post("/api/auth/forgot-password")
def forgot_password_endpoint(payload: ForgotPasswordRequest, request: Request):
    """
    Initiates password reset for staff.
    Anti-enumeration: Always returns a uniform success response regardless of
    whether the email is registered, rate-limited, or any other internal condition.
    Both account-based (3/15 min) and IP-based (10/15 min) rate limits apply silently.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    forwarded_for = request.headers.get("x-forwarded-for")
    return request_password_reset(
        engine, payload.email, client_ip=client_ip, forwarded_for=forwarded_for
    )


@app.post("/api/auth/verify-reset-token")
def verify_token_endpoint(payload: VerifyResetTokenRequest):
    """
    Pre-validates a password reset token before displaying the reset password form.
    Returns 200 with masked email if valid, or 400 if expired, invalid, or already used.
    """
    return verify_reset_token(engine, payload.token)


@app.post("/api/auth/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest, request: Request):
    """
    Executes single-use password reset.
    Validates token, updates password hash using pbkdf2_sha256, and invalidates token atomically.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "MediShop-App")
    return execute_password_reset(
        engine,
        raw_token=payload.token,
        new_password=payload.new_password,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# CURRENT USER IDENTITY ENDPOINT
# Protected with authentication dependency: get_current_user
# Returns the authenticated user's own profile (no credential material).
# ==============================================================================

@app.get("/api/auth/me")
def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.

    The caller identity comes exclusively from the verified Bearer JWT and the
    live database profile — never from client-supplied data.

    Response fields: id, email, full_name, role, is_active.
    Never includes password_hash or any credential material.
    """
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "full_name": current_user.get("full_name") or "",
        "role": current_user["role"],
        "is_active": bool(current_user["is_active"]),
    }


# ==============================================================================
# MEDICINE & INVENTORY ENDPOINTS
# Catalogue read/create/update + inventory/stock reads. Authenticated staff
# may read; create/update (and therefore deactivation) require an active admin.
# ==============================================================================

@app.get("/api/medicines")
def get_medicines(
    search: str = "",
    category_id: str = "",
    brand_id: str = "",
    is_active: Optional[bool] = None,
    page: int = 1,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Returns a paginated, searchable list of medicines.

    Query params:
    - ``search``: partial match on medicine name / generic name.
    - ``category_id`` / ``brand_id``: optional exact filters.
    - ``is_active``: filter by active status (default True for the public catalogue).
    - ``page`` / ``limit``: pagination (limit capped at 100).
    """
    try:
        return medicine_list(
            engine,
            search=search,
            category_id=category_id,
            brand_id=brand_id,
            is_active=is_active,
            page=page,
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the medicine catalogue.",
        ) from exc


@app.get("/api/medicines/{medicine_id}")
def get_medicine(
    medicine_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns a single medicine by ID. Raises HTTP 404 when not found."""
    try:
        return medicine_get(engine, medicine_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the medicine.",
        ) from exc


@app.post("/api/medicines")
def create_medicine(
    payload: MedicineCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new medicine. Requires an active administrator."""
    client_ip, user_agent = _request_meta(request)
    return medicine_create(
        engine,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.patch("/api/medicines/{medicine_id}")
def update_medicine(
    medicine_id: str,
    payload: MedicineUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Partially updates a medicine. Supports deactivation via ``is_active: False``.
    Requires an active administrator. Raises HTTP 404 when not found.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_update(
        engine,
        medicine_id,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.put("/api/medicines/{medicine_id}")
def update_medicine_put(
    medicine_id: str,
    payload: MedicineUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Updates a medicine. Requires an active administrator.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_update(
        engine,
        medicine_id,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.delete("/api/medicines/{medicine_id}")
def delete_medicine(
    medicine_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Deactivates a medicine. Requires an active administrator.
    Rejects pharmacists and unauthorized callers with HTTP 403.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_update(
        engine,
        medicine_id,
        {"is_active": False},
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.get("/api/inventory/medicines/{medicine_id}")
def get_medicine_inventory(
    medicine_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Returns inventory/stock information for a medicine: aggregate current
    stock, low-stock flag, and batch quantities with expiry dates.
    Raises HTTP 404 when the medicine does not exist.
    """
    return medicine_inventory(engine, medicine_id)


@app.get("/api/inventory/medicines")
def get_medicines_inventory(
    search: str = "",
    is_active: bool = True,
    page: int = 1,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Returns a paginated inventory list: each medicine with aggregate current
    stock, low-stock flag, and its batches (quantities + expiry dates).

    Query params:
    - ``search``: partial match on medicine name / generic name.
    - ``is_active``: filter by active status (default True).
    - ``page`` / ``limit``: pagination (limit capped at 100).
    """
    try:
        return medicine_inventory_list(
            engine,
            search=search,
            page=page,
            limit=limit,
            is_active=is_active,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while fetching the inventory.",
        ) from exc


@app.get("/api/categories")
def get_medicine_categories(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns all medicine categories (for filters / forms)."""
    return medicine_categories(engine)


@app.get("/api/brands")
def get_medicine_brands(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns all medicine brands (for filters / forms)."""
    return medicine_brands(engine)


@app.post("/api/categories")
def create_category(
    payload: CategoryCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new medicine category. Requires an active administrator."""
    client_ip, user_agent = _request_meta(request)
    return medicine_category_create(
        engine,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.put("/api/categories/{category_id}")
@app.patch("/api/categories/{category_id}")
def update_category(
    category_id: str,
    payload: CategoryUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Partially updates a medicine category (name, slug, description, storage_temperature).

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when the new name/slug is duplicated.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_category_update(
        engine,
        category_id,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.delete("/api/categories/{category_id}")
def delete_category(
    category_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Deletes a medicine category.

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when medicines still reference the category.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_category_delete(
        engine,
        category_id,
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.post("/api/brands")
def create_brand(
    payload: BrandCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new medicine brand. Requires an active administrator."""
    client_ip, user_agent = _request_meta(request)
    return medicine_brand_create(
        engine,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.put("/api/brands/{brand_id}")
@app.patch("/api/brands/{brand_id}")
def update_brand(
    brand_id: str,
    payload: BrandUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Partially updates a medicine brand (name, manufacturer, contact_email, contact_phone).

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when the new name is duplicated.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_brand_update(
        engine,
        brand_id,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.delete("/api/brands/{brand_id}")
def delete_brand(
    brand_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Deletes a medicine brand.

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when medicines still reference the brand.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_brand_delete(
        engine,
        brand_id,
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.get("/api/batches")
def get_batches(
    search: str = "",
    medicine_id: str = "",
    status_filter: str = "",
    page: int = 1,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Lists batches with optional filtering by search, medicine_id, and expiry/stock status."""
    return medicine_batch_list(
        engine,
        search=search,
        medicine_id=medicine_id,
        status_filter=status_filter,
        page=page,
        limit=limit,
    )


@app.post("/api/batches")
def create_batch(
    payload: BatchCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Creates a new medicine batch (stock intake). Requires an active administrator.

    - Validates the medicine exists, supplier (if supplied), mfg/expiry ordering,
      and selling_price <= mrp.
    - Rejects duplicate (medicine_id, batch_no) with HTTP 409.
    - Sets both ``initial_quantity`` and ``current_quantity`` to the received quantity.
    """
    client_ip, user_agent = _request_meta(request)
    return medicine_batch_create(
        engine,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# USER ROLE & STATUS ADMINISTRATION ENDPOINTS
# Protected with authentication dependency: require_active_admin
# Protected with MySQL named-lock mutex: 'medishop_admin_role_mutex'
# ==============================================================================

@app.patch("/api/users/{user_id}/role")
def update_role(
    user_id: str,
    payload: RoleUpdateRequest,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin)
):
    """
    Updates the role of a user profile.
    Requires verified active administrator authentication.
    Strictly prevents demoting the last active administrator via 'medishop_admin_role_mutex'.
    Audit actor is derived exclusively from the authenticated administrator identity.
    """
    client_ip, user_agent = _request_meta(request)
    actor_id = current_admin["id"]

    return update_user_role_or_status(
        engine=engine,
        target_user_id=user_id,
        new_role=payload.role,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
        actor=current_admin,
    )


@app.patch("/api/users/{user_id}/status")
def update_status(
    user_id: str,
    payload: StatusUpdateRequest,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin)
):
    """
    Updates the active status (activation/deactivation) of a user profile.
    Requires verified active administrator authentication.
    Strictly prevents deactivating the last active administrator via 'medishop_admin_role_mutex'.
    Audit actor is derived exclusively from the authenticated administrator identity.
    """
    client_ip, user_agent = _request_meta(request)
    actor_id = current_admin["id"]

    return update_user_role_or_status(
        engine=engine,
        target_user_id=user_id,
        new_is_active=payload.is_active,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
        actor=current_admin,
    )


@app.patch("/api/users/{user_id}")
def update_role_or_status_combined(
    user_id: str,
    payload: UserRoleStatusUpdateRequest,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin)
):
    """
    Combined endpoint to update role and/or active status in a single atomic transaction.
    Requires verified active administrator authentication.
    Audit actor is derived exclusively from the authenticated administrator identity.
    """
    client_ip, user_agent = _request_meta(request)
    actor_id = current_admin["id"]

    return update_user_role_or_status(
        engine=engine,
        target_user_id=user_id,
        new_role=payload.role,
        new_is_active=payload.is_active,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
        actor=current_admin,
    )


# ==============================================================================
# SUPPLIERS ENDPOINTS
# ==============================================================================

@app.get("/api/suppliers")
def get_suppliers(
    search: str = "",
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns suppliers, optionally filtered by search. Requires active admin."""
    return supplier_list(engine, search=search)


@app.get("/api/suppliers/{supplier_id}")
def get_supplier(
    supplier_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Retrieves a single supplier by ID. Requires active admin."""
    return supplier_get(engine, supplier_id)


@app.post("/api/suppliers")
def create_supplier(
    payload: SupplierCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new supplier. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return supplier_create(
        engine,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.put("/api/suppliers/{supplier_id}")
@app.patch("/api/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: str,
    payload: SupplierUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Updates an existing supplier. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return supplier_update(
        engine,
        supplier_id,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(
    supplier_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Deletes a supplier. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return supplier_delete(
        engine,
        supplier_id,
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# CUSTOMERS ENDPOINTS
# ==============================================================================

@app.get("/api/customers")
def get_customers(
    search: str = "",
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns customers, optionally filtered by search."""
    return customer_list(engine, search=search)


@app.get("/api/customers/{customer_id}")
def get_customer(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Retrieves a single customer by ID."""
    return customer_get(engine, customer_id)


@app.post("/api/customers")
def create_customer(
    payload: CustomerCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Creates a new customer."""
    client_ip, user_agent = _request_meta(request)
    return customer_create(
        engine,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.put("/api/customers/{customer_id}")
@app.patch("/api/customers/{customer_id}")
def update_customer(
    customer_id: str,
    payload: CustomerUpdateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Updates an existing customer profile."""
    client_ip, user_agent = _request_meta(request)
    return customer_update(
        engine,
        customer_id,
        payload.model_dump(),
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.delete("/api/customers/{customer_id}")
def delete_customer(
    customer_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Deletes a customer profile. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return customer_delete(
        engine,
        customer_id,
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# INVOICES / POS ENDPOINTS
# ==============================================================================

@app.get("/api/invoices")
def get_invoices(
    search: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns a paginated list of sales invoices."""
    return invoice_list(
        engine,
        search=search,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )


@app.get("/api/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Retrieves an invoice and its line items.
    Protects wholesale purchase costs: purchase_cost_at_sale is stripped for non-admin callers.
    """
    invoice_data = invoice_get(engine, invoice_id)
    if current_user.get("role") != "admin" and "items" in invoice_data:
        # Non-admin users (such as pharmacists) should not see internal purchase costs
        for item in invoice_data["items"]:
            item.pop("purchase_cost_at_sale", None)
    return invoice_data


@app.post("/api/invoices")
def create_invoice(
    payload: InvoiceCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Creates a counter sale invoice, deducts inventory, and records ledger movements atomically.
    """
    client_ip, user_agent = _request_meta(request)
    return invoice_create(
        engine,
        payload.model_dump(),
        created_by=current_user["id"],
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# PURCHASES / INWARD PROCUREMENT ENDPOINTS
# ==============================================================================

@app.get("/api/purchases")
def get_purchases(
    search: str = "",
    page: int = 1,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns a paginated list of purchases. Requires active admin."""
    return purchase_list(engine, search=search, page=page, limit=limit)


@app.get("/api/purchases/{purchase_id}")
def get_purchase(
    purchase_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Retrieves a purchase record with items. Requires active admin."""
    return purchase_get(engine, purchase_id)


@app.post("/api/purchases")
def create_purchase(
    payload: PurchaseCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Records an inward purchase bill, updates or inserts batches, and writes stock_movements.
    """
    client_ip, user_agent = _request_meta(request)
    return purchase_create(
        engine,
        payload.model_dump(),
        created_by=current_user["id"],
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# EXPENSES ENDPOINTS
# ==============================================================================

@app.get("/api/expenses")
def get_expenses(
    search: str = "",
    category: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns a paginated list of operating expenses. Requires active admin."""
    return expense_list(
        engine,
        search=search,
        category=category,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
    )


@app.post("/api/expenses")
def create_expense(
    payload: ExpenseCreateRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new expense entry. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return expense_create(
        engine,
        payload.model_dump(),
        created_by=current_user["id"],
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.delete("/api/expenses/{expense_id}")
def delete_expense(
    expense_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Deletes an expense entry. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return expense_delete(
        engine,
        expense_id,
        actor=current_user,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# USER & STAFF MANAGEMENT ENDPOINTS
# ==============================================================================

@app.get("/api/users")
def get_users(
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Lists all user accounts. Requires active admin."""
    return user_list(engine)


@app.post("/api/users")
def create_user(
    payload: UserCreateRequest,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new user profile with password hash. Requires active admin."""
    client_ip, user_agent = _request_meta(request)
    return user_create(
        engine,
        payload.model_dump(),
        created_by=current_admin["id"],
        actor=current_admin,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.post("/api/users/restore")
def restore_user(
    payload: UserRestoreRequest,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Restores a previously deleted account, inactive until an admin activates it."""
    client_ip, user_agent = _request_meta(request)
    return restore_user_account(
        engine,
        payload.email,
        actor_user_id=current_admin["id"],
        actor=current_admin,
        client_ip=client_ip,
        user_agent=user_agent,
    )


@app.post("/api/users/{user_id}/unlock")
def unlock_account(
    user_id: str,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Unlocks a locked user account and resets its failed-login counter.

    Requires a verified active administrator. Rejects ordinary authenticated
    users (403) and unauthenticated requests (401) via the authorization
    dependency; returns 404 when the target account does not exist.
    """
    client_ip, user_agent = _request_meta(request)
    actor_id = current_admin["id"]

    return unlock_user_account(
        engine=engine,
        target_user_id=user_id,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
        actor=current_admin,
    )


@app.delete("/api/users/{user_id}")
def delete_user(
    user_id: str,
    request: Request,
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Soft-deletes an eligible staff account while retaining historical identity.

    Requires an active administrator.  Rejects non-admin authenticated users
    (403) and unauthenticated requests (401) through ``require_active_admin``.
    Self-deletion (403) and deleting the last active administrator (403) are
    refused. Eligible accounts are soft-deleted, preserving historical records.
    """
    client_ip, user_agent = _request_meta(request)

    return delete_user_account(
        engine=engine,
        target_user_id=user_id,
        actor_user_id=current_admin["id"],
        client_ip=client_ip,
        user_agent=user_agent,
        actor=current_admin,
    )


# ==============================================================================
# AUDIT LOG ENDPOINTS (read-only, active administrators only)
# ==============================================================================

def _validate_audit_date(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    value = str(value).strip()
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must use YYYY-MM-DD format.",
        ) from exc
    return value


@app.get("/api/audit-logs")
def get_audit_logs(
    search: str = "",
    module: str = "",
    action: str = "",
    entity_type: str = "",
    entity_id: str = "",
    user_id: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns a paginated, filtered audit-log list. Requires active admin."""
    start_date = _validate_audit_date(start_date, "start_date")
    end_date = _validate_audit_date(end_date, "end_date")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be on or before end_date.",
        )
    return audit_service.audit_log_list(
        engine,
        page=page,
        limit=limit,
        search=search,
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )


@app.get("/api/audit-logs/options")
def get_audit_log_options(
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns distinct modules, actions, and actors for audit filters."""
    return audit_service.audit_log_options(engine)


@app.get("/api/audit-logs/{audit_id}")
def get_audit_log(
    audit_id: str,
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns one audit-log entry with its sanitized old/new values."""
    entry = audit_service.audit_log_get(engine, audit_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log entry not found.",
        )
    return entry


# ==============================================================================
# DASHBOARD & REPORTS ENDPOINTS
# ==============================================================================

@app.get("/api/dashboard/stats")
def get_dashboard_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns executive dashboard statistics."""
    return dashboard_stats(engine)


@app.get("/api/reports/summary")
def get_reports_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Returns financial and operational reports summary. Requires active administrator."""
    return reports_summary(engine, start_date=start_date, end_date=end_date)


# ==============================================================================
@app.post("/api/admin/email-settings/test")
def test_active_email_provider_endpoint(
    payload: ProviderTestEmailRequest,
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Sends a test message through the active Brevo sender identity."""
    return send_test_email(payload.recipient_email, engine)


@app.get("/api/admin/email-settings")
def get_email_settings_endpoint(current_admin: Dict[str, Any] = Depends(require_active_admin)):
    return {
        "provider": "brevo",
        "brevo_configured": bool(os.getenv("BREVO_API_KEY", "").strip()),
        "senders": email_sender_service.list_senders(engine),
    }


@app.post("/api/admin/email-senders")
def create_email_sender_endpoint(payload: EmailSenderCreateRequest,
                                current_admin: Dict[str, Any] = Depends(require_active_admin)):
    return email_sender_service.add_sender(engine, payload.model_dump())


@app.put("/api/admin/email-senders/{sender_id}")
def update_email_sender_endpoint(sender_id: str, payload: EmailSenderCreateRequest,
                                current_admin: Dict[str, Any] = Depends(require_active_admin)):
    return email_sender_service.update_sender(engine, sender_id, payload.model_dump())


@app.post("/api/admin/email-senders/{sender_id}/verify")
def verify_email_sender_endpoint(sender_id: str, payload: EmailSenderVerifyRequest,
                                 current_admin: Dict[str, Any] = Depends(require_active_admin)):
    return email_sender_service.mark_sender_verified(engine, sender_id, payload.confirm_brevo_verified)


@app.post("/api/admin/email-senders/{sender_id}/activate")
def activate_email_sender_endpoint(sender_id: str,
                                   current_admin: Dict[str, Any] = Depends(require_active_admin)):
    return email_sender_service.activate_sender(engine, sender_id)


@app.post("/api/admin/email-senders/{sender_id}/disable")
def disable_email_sender_endpoint(sender_id: str,
                                  current_admin: Dict[str, Any] = Depends(require_active_admin)):
    return email_sender_service.disable_sender(engine, sender_id)
