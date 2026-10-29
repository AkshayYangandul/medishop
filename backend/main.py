from typing import Optional, Dict, Any
from fastapi import FastAPI, Response, Request, Depends, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text

try:
    from database import engine, test_connection
    from user_service import update_user_role_or_status
    from auth import require_active_admin, create_access_token, verify_password
except ImportError:
    from backend.database import engine, test_connection
    from backend.user_service import update_user_role_or_status
    from backend.auth import require_active_admin, create_access_token, verify_password

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
