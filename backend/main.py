from typing import Optional, Dict, Any, List
from datetime import date
from decimal import Decimal
from fastapi import FastAPI, Response, Request, Depends, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

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
except ImportError:
    from backend.database import engine, test_connection
    from backend.user_service import update_user_role_or_status, user_list, user_create
    from backend.auth import get_current_user, require_active_admin, create_access_token, verify_password
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
    role: str = Field("cashier", min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = True


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

@app.post("/api/auth/login")
def login(payload: LoginRequest):
    """
    Authenticates an active user against the database and returns a signed Bearer token.
    Rejects inactive users and invalid credentials.
    """
    try:
        with engine.connect() as conn:
            profile = conn.execute(
                text("SELECT id, email, password_hash, role, is_active FROM profiles WHERE email = :email"),
                {"email": payload.email}
            ).mappings().first()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal database error occurred during login."
        )

    if not profile or not verify_password(payload.password, profile["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
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
    return medicine_get(engine, medicine_id)


@app.post("/api/medicines")
def create_medicine(
    payload: MedicineCreateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new medicine. Requires an active administrator."""
    return medicine_create(engine, payload.model_dump())


@app.patch("/api/medicines/{medicine_id}")
def update_medicine(
    medicine_id: str,
    payload: MedicineUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Partially updates a medicine. Supports deactivation via ``is_active: False``.
    Requires an active administrator. Raises HTTP 404 when not found.
    """
    return medicine_update(engine, medicine_id, payload.model_dump())


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
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new medicine category. Requires an active administrator."""
    return medicine_category_create(engine, payload.model_dump())


@app.put("/api/categories/{category_id}")
@app.patch("/api/categories/{category_id}")
def update_category(
    category_id: str,
    payload: CategoryUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Partially updates a medicine category (name, slug, description, storage_temperature).

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when the new name/slug is duplicated.
    """
    return medicine_category_update(engine, category_id, payload.model_dump())


@app.delete("/api/categories/{category_id}")
def delete_category(
    category_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Deletes a medicine category.

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when medicines still reference the category.
    """
    return medicine_category_delete(engine, category_id)


@app.post("/api/brands")
def create_brand(
    payload: BrandCreateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new medicine brand. Requires an active administrator."""
    return medicine_brand_create(engine, payload.model_dump())


@app.put("/api/brands/{brand_id}")
@app.patch("/api/brands/{brand_id}")
def update_brand(
    brand_id: str,
    payload: BrandUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Partially updates a medicine brand (name, manufacturer, contact_email, contact_phone).

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when the new name is duplicated.
    """
    return medicine_brand_update(engine, brand_id, payload.model_dump())


@app.delete("/api/brands/{brand_id}")
def delete_brand(
    brand_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Deletes a medicine brand.

    Requires an active administrator. Raises HTTP 404 when not found and
    HTTP 409 when medicines still reference the brand.
    """
    return medicine_brand_delete(engine, brand_id)


@app.get("/api/batches")
def get_batches(
    search: str = "",
    medicine_id: str = "",
    status_filter: str = "",
    page: int = 1,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user),
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
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Creates a new medicine batch (stock intake). Requires an active administrator.

    - Validates the medicine exists, supplier (if supplied), mfg/expiry ordering,
      and selling_price <= mrp.
    - Rejects duplicate (medicine_id, batch_no) with HTTP 409.
    - Sets both ``initial_quantity`` and ``current_quantity`` to the received quantity.
    """
    return medicine_batch_create(engine, payload.model_dump())


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
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "MediShop-App")
    actor_id = current_admin["id"]

    return update_user_role_or_status(
        engine=engine,
        target_user_id=user_id,
        new_role=payload.role,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
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
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "MediShop-App")
    actor_id = current_admin["id"]

    return update_user_role_or_status(
        engine=engine,
        target_user_id=user_id,
        new_is_active=payload.is_active,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
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
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "MediShop-App")
    actor_id = current_admin["id"]

    return update_user_role_or_status(
        engine=engine,
        target_user_id=user_id,
        new_role=payload.role,
        new_is_active=payload.is_active,
        actor_user_id=actor_id,
        client_ip=client_ip,
        user_agent=user_agent,
    )


# ==============================================================================
# SUPPLIERS ENDPOINTS
# ==============================================================================

@app.get("/api/suppliers")
def get_suppliers(
    search: str = "",
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns suppliers, optionally filtered by search."""
    return supplier_list(engine, search=search)


@app.get("/api/suppliers/{supplier_id}")
def get_supplier(
    supplier_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Retrieves a single supplier by ID."""
    return supplier_get(engine, supplier_id)


@app.post("/api/suppliers")
def create_supplier(
    payload: SupplierCreateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new supplier. Requires active admin."""
    return supplier_create(engine, payload.model_dump())


@app.put("/api/suppliers/{supplier_id}")
@app.patch("/api/suppliers/{supplier_id}")
def update_supplier(
    supplier_id: str,
    payload: SupplierUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Updates an existing supplier. Requires active admin."""
    return supplier_update(engine, supplier_id, payload.model_dump())


@app.delete("/api/suppliers/{supplier_id}")
def delete_supplier(
    supplier_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Deletes a supplier. Requires active admin."""
    return supplier_delete(engine, supplier_id)


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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Creates a new customer."""
    return customer_create(engine, payload.model_dump())


@app.put("/api/customers/{customer_id}")
@app.patch("/api/customers/{customer_id}")
def update_customer(
    customer_id: str,
    payload: CustomerUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Updates an existing customer profile."""
    return customer_update(engine, customer_id, payload.model_dump())


@app.delete("/api/customers/{customer_id}")
def delete_customer(
    customer_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Deletes a customer profile. Requires active admin."""
    return customer_delete(engine, customer_id)


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
    """Retrieves an invoice and its line items."""
    return invoice_get(engine, invoice_id)


@app.post("/api/invoices")
def create_invoice(
    payload: InvoiceCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Creates a counter sale invoice, deducts inventory, and records ledger movements atomically.
    """
    return invoice_create(engine, payload.model_dump(), created_by=current_user["id"])


# ==============================================================================
# PURCHASES / INWARD PROCUREMENT ENDPOINTS
# ==============================================================================

@app.get("/api/purchases")
def get_purchases(
    search: str = "",
    page: int = 1,
    limit: int = 50,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns a paginated list of purchases."""
    return purchase_list(engine, search=search, page=page, limit=limit)


@app.get("/api/purchases/{purchase_id}")
def get_purchase(
    purchase_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Retrieves a purchase record with items."""
    return purchase_get(engine, purchase_id)


@app.post("/api/purchases")
def create_purchase(
    payload: PurchaseCreateRequest,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """
    Records an inward purchase bill, updates or inserts batches, and writes stock_movements.
    """
    return purchase_create(engine, payload.model_dump(), created_by=current_user["id"])


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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns a paginated list of operating expenses."""
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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Creates a new expense entry."""
    return expense_create(engine, payload.model_dump(), created_by=current_user["id"])


@app.delete("/api/expenses/{expense_id}")
def delete_expense(
    expense_id: str,
    current_user: Dict[str, Any] = Depends(require_active_admin),
):
    """Deletes an expense entry. Requires active admin."""
    return expense_delete(engine, expense_id)


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
    current_admin: Dict[str, Any] = Depends(require_active_admin),
):
    """Creates a new user profile with password hash. Requires active admin."""
    return user_create(engine, payload.model_dump(), created_by=current_admin["id"])


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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Returns financial and operational reports summary."""
    return reports_summary(engine, start_date=start_date, end_date=end_date)
