warning: in the working copy of 'backend/main.py', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/backend/main.py b/backend/main.py[m
[1mindex ae96101..640b3bd 100644[m
[1m--- a/backend/main.py[m
[1m+++ b/backend/main.py[m
[36m@@ -1,4 +1,5 @@[m
 from typing import Optional, Dict, Any[m
[32m+[m[32mfrom datetime import date[m
 from fastapi import FastAPI, Response, Request, Depends, status, HTTPException[m
 from fastapi.middleware.cors import CORSMiddleware[m
 from pydantic import BaseModel, Field[m
[36m@@ -7,11 +8,37 @@[m [mfrom sqlalchemy import text[m
 try:[m
     from database import engine, test_connection[m
     from user_service import update_user_role_or_status[m
[31m-    from auth import require_active_admin, create_access_token, verify_password[m
[32m+[m[32m    from auth import get_current_user, require_active_admin, create_access_token, verify_password[m
[32m+[m[32m    from medicine_service import ([m
[32m+[m[32m        medicine_batch_create,[m
[32m+[m[32m        medicine_create,[m
[32m+[m[32m        medicine_get,[m
[32m+[m[32m        medicine_inventory,[m
[32m+[m[32m        medicine_list,[m
[32m+[m[32m        medicine_update,[m
[32m+[m[32m    )[m
[32m+[m[32m    from medicine_service import ([m
[32m+[m[32m        medicine_brands,[m
[32m+[m[32m        medicine_categories,[m
[32m+[m[32m        medicine_inventory_list,[m
[32m+[m[32m    )[m
 except ImportError:[m
     from backend.database import engine, test_connection[m
     from backend.user_service import update_user_role_or_status[m
[31m-    from backend.auth import require_active_admin, create_access_token, verify_password[m
[32m+[m[32m    from backend.auth import get_current_user, require_active_admin, create_access_token, verify_password[m
[32m+[m[32m    from backend.medicine_service import ([m
[32m+[m[32m        medicine_batch_create,[m
[32m+[m[32m        medicine_create,[m
[32m+[m[32m        medicine_get,[m
[32m+[m[32m        medicine_inventory,[m
[32m+[m[32m        medicine_list,[m
[32m+[m[32m        medicine_update,[m
[32m+[m[32m    )[m
[32m+[m[32m    from backend.medicine_service import ([m
[32m+[m[32m        medicine_brands,[m
[32m+[m[32m        medicine_categories,[m
[32m+[m[32m        medicine_inventory_list,[m
[32m+[m[32m    )[m
 [m
 # Initialize FastAPI application[m
 app = FastAPI([m
[36m@@ -54,6 +81,45 @@[m [mclass UserRoleStatusUpdateRequest(BaseModel):[m
     is_active: Optional[bool] = Field(None, description="Target active status")[m
 [m
 [m
[32m+[m[32mclass MedicineCreateRequest(BaseModel):[m
[32m+[m[32m    name: str = Field(..., min_length=1, max_length=255, description="Medicine name")[m
[32m+[m[32m    generic_name: Optional[str] = Field(None, max_length=255, description="Generic drug name")[m
[32m+[m[32m    category_id: str = Field(..., min_length=1, max_length=64, description="Category ID (FK)")[m
[32m+[m[32m    brand_id: Optional[str] = Field(None, max_length=64, description="Brand ID (FK, optional)")[m
[32m+[m[32m    dosage_form: str = Field(..., description="Dosage form: 'Tablet', 'Capsule', 'Syrup', 'Injection', 'Ointment', 'Drops', 'Inhaler', 'Other'")[m
[32m+[m[32m    strength: Optional[str] = Field(None, max_length=100, description="Strength / dosage strength")[m
[32m+[m[32m    unit: str = Field("Strip", max_length=50, description="Stock unit, default 'Strip'")[m
[32m+[m[32m    hsn_code: Optional[str] = Field(None, max_length=50, description="HSN code")[m
[32m+[m[32m    requires_prescription: bool = Field(False, description="Whether prescription is required")[m
[32m+[m[32m    min_stock_alert: int = Field(10, ge=0, description="Low-stock alert threshold")[m
[32m+[m
[32m+[m
[32m+[m[32mclass MedicineUpdateRequest(BaseModel):[m
[32m+[m[32m    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Medicine name")[m
[32m+[m[32m    generic_name: Optional[str] = Field(None, max_length=255, description="Generic drug name")[m
[32m+[m[32m    category_id: Optional[str] = Field(None, min_length=1, max_length=64, description="Category ID (FK)")[m
[32m+[m[32m    brand_id: Optional[str] = Field(None, max_length=64, description="Brand ID (FK, optional)")[m
[32m+[m[32m    dosage_form: Optional[str] = Field(None, max_length=100, description="Dosage form")[m
[32m+[m[32m    strength: Optional[str] = Field(None, max_length=100, description="Strength / dosage strength")[m
[32m+[m[32m    unit: Optional[str] = Field(None, max_length=50, description="Stock unit")[m
[32m+[m[32m    hsn_code: Optional[str] = Field(None, max_length=50, description="HSN code")[m
[32m+[m[32m    requires_prescription: Optional[bool] = Field(None, description="Whether prescription is required")[m
[32m+[m[32m    min_stock_alert: Optional[int] = Field(None, ge=0, description="Low-stock alert threshold")[m
[32m+[m[32m    is_active: Optional[bool] = Field(None, description="Active status (enables deactivation)")[m
[32m+[m
[32m+[m
[32m+[m[32mclass BatchCreateRequest(BaseModel):[m
[32m+[m[32m    medicine_id: str = Field(..., min_length=1, max_length=64, description="Medicine ID (FK)")[m
[32m+[m[32m    batch_no: str = Field(..., min_length=1, max_length=100, description="Batch number")[m
[32m+[m[32m    mfg_date: Optional[date] = Field(None, description="Manufacture date (optional)")[m
[32m+[m[32m    expiry_date: date = Field(..., description="Expiry date (required)")[m
[32m+[m[32m    purchase_cost: float = Field(..., ge=0, description="Purchase cost (non-negative)")[m
[32m+[m[32m    mrp: float = Field(..., ge=0, description="Maximum retail price (non-negative)")[m
[32m+[m[32m    selling_price: float = Field(..., ge=0, description="Selling price (non-negative)")[m
[32m+[m[32m    initial_quantity: int = Field(..., ge=0, description="Received quantity (non-negative)")[m
[32m+[m[32m    supplier_id: Optional[str] = Field(None, max_length=64, description="Supplier ID (optional)")[m
[32m+[m
[32m+[m
 # ==============================================================================[m
 # BASE SYSTEM & HEALTH ENDPOINTS[m
 # ==============================================================================[m
[36m@@ -153,6 +219,186 @@[m [mdef login(payload: LoginRequest):[m
     }[m
 [m
 [m
[32m+[m[32m# ==============================================================================[m
[32m+[m[32m# CURRENT USER IDENTITY ENDPOINT[m
[32m+[m[32m# Protected with authentication dependency: get_current_user[m
[32m+[m[32m# Returns the authenticated user's own profile (no credential material).[m
[32m+[m[32m# ==============================================================================[m
[32m+[m
[32m+[m[32m@app.get("/api/auth/me")[m
[32m+[m[32mdef get_me(current_user: Dict[str, Any] = Depends(get_current_user)):[m
[32m+[m[32m    """[m
[32m+[m[32m    Returns the profile of the currently authenticated user.[m
[32m+[m
[32m+[m[32m    The caller identity comes exclusively from the verified Bearer JWT and the[m
[32m+[m[32m    live database profile — never from client-supplied data.[m
[32m+[m
[32m+[m[32m    Response fields: id, email, full_name, role, is_active.[m
[32m+[m[32m    Never includes password_hash or any credential material.[m
[32m+[m[32m    """[m
[32m+[m[32m    return {[m
[32m+[m[32m        "id": current_user["id"],[m
[32m+[m[32m        "email": current_user["email"],[m
[32m+[m[32m        "full_name": current_user.get("full_name") or "",[m
[32m+[m[32m        "role": current_user["role"],[m
[32m+[m[32m        "is_active": bool(current_user["is_active"]),[m
[32m+[m[32m    }[m
[32m+[m
[32m+[m
[32m+[m[32m# ==============================================================================[m
[32m+[m[32m# MEDICINE & INVENTORY ENDPOINTS[m
[32m+[m[32m# Catalogue read/create/update + inventory/stock reads. Authenticated staff[m
[32m+[m[32m# may read; create/update (and therefore deactivation) require an active admin.[m
[32m+[m[32m# ==============================================================================[m
[32m+[m
[32m+[m[32m@app.get("/api/medicines")[m
[32m+[m[32mdef get_medicines([m
[32m+[m[32m    search: str = "",[m
[32m+[m[32m    category_id: str = "",[m
[32m+[m[32m    brand_id: str = "",[m
[32m+[m[32m    is_active: bool = True,[m
[32m+[m[32m    page: int = 1,[m
[32m+[m[32m    limit: int = 20,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(get_current_user),[m
[32m+[m[32m):[m
[32m+[m[32m    """[m
[32m+[m[32m    Returns a paginated, searchable list of medicines.[m
[32m+[m
[32m+[m[32m    Query params:[m
[32m+[m[32m    - ``search``: partial match on medicine name / generic name.[m
[32m+[m[32m    - ``category_id`` / ``brand_id``: optional exact filters.[m
[32m+[m[32m    - ``is_active``: filter by active status (default True for the public catalogue).[m
[32m+[m[32m    - ``page`` / ``limit``: pagination (limit capped at 100).[m
[32m+[m[32m    """[m
[32m+[m[32m    try:[m
[32m+[m[32m        return medicine_list([m
[32m+[m[32m            engine,[m
[32m+[m[32m            search=search,[m
[32m+[m[32m            category_id=category_id,[m
[32m+[m[32m            brand_id=brand_id,[m
[32m+[m[32m            is_active=is_active,[m
[32m+[m[32m            page=page,[m
[32m+[m[32m            limit=limit,[m
[32m+[m[32m        )[m
[32m+[m[32m    except HTTPException:[m
[32m+[m[32m        raise[m
[32m+[m[32m    except Exception as exc:[m
[32m+[m[32m        raise HTTPException([m
[32m+[m[32m            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,[m
[32m+[m[32m            detail="An internal error occurred while fetching the medicine catalogue.",[m
[32m+[m[32m        ) from exc[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/api/medicines/{medicine_id}")[m
[32m+[m[32mdef get_medicine([m
[32m+[m[32m    medicine_id: str,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(get_current_user),[m
[32m+[m[32m):[m
[32m+[m[32m    """Returns a single medicine by ID. Raises HTTP 404 when not found."""[m
[32m+[m[32m    return medicine_get(engine, medicine_id)[m
[32m+[m
[32m+[m
[32m+[m[32m@app.post("/api/medicines")[m
[32m+[m[32mdef create_medicine([m
[32m+[m[32m    payload: MedicineCreateRequest,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(require_active_admin),[m
[32m+[m[32m):[m
[32m+[m[32m    """Creates a new medicine. Requires an active administrator."""[m
[32m+[m[32m    return medicine_create(engine, payload.model_dump())[m
[32m+[m
[32m+[m
[32m+[m[32m@app.patch("/api/medicines/{medicine_id}")[m
[32m+[m[32mdef update_medicine([m
[32m+[m[32m    medicine_id: str,[m
[32m+[m[32m    payload: MedicineUpdateRequest,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(require_active_admin),[m
[32m+[m[32m):[m
[32m+[m[32m    """[m
[32m+[m[32m    Partially updates a medicine. Supports deactivation via ``is_active: False``.[m
[32m+[m[32m    Requires an active administrator. Raises HTTP 404 when not found.[m
[32m+[m[32m    """[m
[32m+[m[32m    return medicine_update(engine, medicine_id, payload.model_dump())[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/api/inventory/medicines/{medicine_id}")[m
[32m+[m[32mdef get_medicine_inventory([m
[32m+[m[32m    medicine_id: str,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(get_current_user),[m
[32m+[m[32m):[m
[32m+[m[32m    """[m
[32m+[m[32m    Returns inventory/stock information for a medicine: aggregate current[m
[32m+[m[32m    stock, low-stock flag, and batch quantities with expiry dates.[m
[32m+[m[32m    Raises HTTP 404 when the medicine does not exist.[m
[32m+[m[32m    """[m
[32m+[m[32m    return medicine_inventory(engine, medicine_id)[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/api/inventory/medicines")[m
[32m+[m[32mdef get_medicines_inventory([m
[32m+[m[32m    search: str = "",[m
[32m+[m[32m    is_active: bool = True,[m
[32m+[m[32m    page: int = 1,[m
[32m+[m[32m    limit: int = 20,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(get_current_user),[m
[32m+[m[32m):[m
[32m+[m[32m    """[m
[32m+[m[32m    Returns a paginated inventory list: each medicine with aggregate current[m
[32m+[m[32m    stock, low-stock flag, and its batches (quantities + expiry dates).[m
[32m+[m
[32m+[m[32m    Query params:[m
[32m+[m[32m    - ``search``: partial match on medicine name / generic name.[m
[32m+[m[32m    - ``is_active``: filter by active status (default True).[m
[32m+[m[32m    - ``page`` / ``limit``: pagination (limit capped at 100).[m
[32m+[m[32m    """[m
[32m+[m[32m    try:[m
[32m+[m[32m        return medicine_inventory_list([m
[32m+[m[32m            engine,[m
[32m+[m[32m            search=search,[m
[32m+[m[32m            page=page,[m
[32m+[m[32m            limit=limit,[m
[32m+[m[32m            is_active=is_active,[m
[32m+[m[32m        )[m
[32m+[m[32m    except HTTPException:[m
[32m+[m[32m        raise[m
[32m+[m[32m    except Exception as exc:[m
[32m+[m[32m        raise HTTPException([m
[32m+[m[32m            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,[m
[32m+[m[32m            detail="An internal error occurred while fetching the inventory.",[m
[32m+[m[32m        ) from exc[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/api/categories")[m
[32m+[m[32mdef get_medicine_categories([m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(get_current_user),[m
[32m+[m[32m):[m
[32m+[m[32m    """Returns all medicine categories (for filters / forms)."""[m
[32m+[m[32m    return medicine_categories(engine)[m
[32m+[m
[32m+[m
[32m+[m[32m@app.get("/api/brands")[m
[32m+[m[32mdef get_medicine_brands([m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(get_current_user),[m
[32m+[m[32m):[m
[32m+[m[32m    """Returns all medicine brands (for filters / forms)."""[m
[32m+[m[32m    return medicine_brands(engine)[m
[32m+[m
[32m+[m
[32m+[m[32m@app.post("/api/batches")[m
[32m+[m[32mdef create_batch([m
[32m+[m[32m    payload: BatchCreateRequest,[m
[32m+[m[32m    current_user: Dict[str, Any] = Depends(require_active_admin),[m
[32m+[m[32m):[m
[32m+[m[32m    """[m
[32m+[m[32m    Creates a new medicine batch (stock intake). Requires an active administrator.[m
[32m+[m
[32m+[m[32m    - Validates the medicine exists, supplier (if supplied), mfg/expiry ordering,[m
[32m+[m[32m      and selling_price <= mrp.[m
[32m+[m[32m    - Rejects duplicate (medicine_id, batch_no) with HTTP 409.[m
[32m+[m[32m    - Sets both ``initial_quantity`` and ``current_quantity`` to the received quantity.[m
[32m+[m[32m    """[m
[32m+[m[32m    return medicine_batch_create(engine, payload.model_dump())[m
[32m+[m
[32m+[m
 # ==============================================================================[m
 # USER ROLE & STATUS ADMINISTRATION ENDPOINTS[m
 # Protected with authentication dependency: require_active_admin[m
