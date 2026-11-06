"""
MediShop Audit Service
======================
Centralised, backend-only audit trail helpers.

Design notes
------------
* Audit rows are written on the caller's existing SQLAlchemy connection so the
  business mutation and its audit event commit or roll back together.
* The authenticated, database-backed user profile is the only accepted source
  of actor identity.  Request bodies and query strings are never trusted for
  actor information.
* Sensitive keys are redacted recursively before JSON is persisted.  Services
  should still pass explicit field dictionaries rather than raw payloads.
* Retrieval is read-only.  There are deliberately no update/delete helpers.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

# ---------------------------------------------------------------------------
# Canonical module / action catalog
# ---------------------------------------------------------------------------

MODULE_AUTH = "auth"
MODULE_USERS = "users"
MODULE_INVENTORY = "inventory"
MODULE_CATALOGUE = "catalogue"
MODULE_PROCUREMENT = "procurement"
MODULE_SALES = "sales"
MODULE_FINANCE = "finance"
MODULE_SYSTEM = "system"

MODULES = (
    MODULE_AUTH,
    MODULE_USERS,
    MODULE_INVENTORY,
    MODULE_CATALOGUE,
    MODULE_PROCUREMENT,
    MODULE_SALES,
    MODULE_FINANCE,
    MODULE_SYSTEM,
)

ACTION_LOGIN_SUCCESS = "LOGIN_SUCCESS"
ACTION_LOGIN_FAILED = "LOGIN_FAILED"
ACTION_ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
ACTION_PASSWORD_RESET_SUCCESS = "PASSWORD_RESET_SUCCESS"

ACTION_USER_CREATED = "USER_CREATED"
ACTION_ROLE_OR_STATUS_CHANGE = "ROLE_OR_STATUS_CHANGE"
ACTION_ACCOUNT_UNLOCK = "ACCOUNT_UNLOCK"
ACTION_ACCOUNT_DELETE = "ACCOUNT_DELETE"
ACTION_ACCOUNT_RESTORE = "ACCOUNT_RESTORE"
ACTION_INITIAL_ADMIN_PROVISIONING = "INITIAL_ADMIN_PROVISIONING"

ACTION_MEDICINE_CREATED = "MEDICINE_CREATED"
ACTION_MEDICINE_UPDATED = "MEDICINE_UPDATED"
ACTION_MEDICINE_DEACTIVATED = "MEDICINE_DEACTIVATED"
ACTION_BATCH_CREATED = "BATCH_CREATED"

ACTION_CATEGORY_CREATED = "CATEGORY_CREATED"
ACTION_CATEGORY_UPDATED = "CATEGORY_UPDATED"
ACTION_CATEGORY_DELETED = "CATEGORY_DELETED"
ACTION_BRAND_CREATED = "BRAND_CREATED"
ACTION_BRAND_UPDATED = "BRAND_UPDATED"
ACTION_BRAND_DELETED = "BRAND_DELETED"

ACTION_SUPPLIER_CREATED = "SUPPLIER_CREATED"
ACTION_SUPPLIER_UPDATED = "SUPPLIER_UPDATED"
ACTION_SUPPLIER_DELETED = "SUPPLIER_DELETED"
ACTION_PURCHASE_CREATED = "PURCHASE_CREATED"

ACTION_CUSTOMER_CREATED = "CUSTOMER_CREATED"
ACTION_CUSTOMER_UPDATED = "CUSTOMER_UPDATED"
ACTION_CUSTOMER_DELETED = "CUSTOMER_DELETED"
ACTION_INVOICE_CREATED = "INVOICE_CREATED"

ACTION_EXPENSE_CREATED = "EXPENSE_CREATED"
ACTION_EXPENSE_DELETED = "EXPENSE_DELETED"

# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------

_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|authorization|api[_-]?key|"
    r"smtp|app[_-]?password|otp|credential|private[_-]?key)",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"
_MAX_STRING_LENGTH = 2000
_MAX_COLLECTION_ITEMS = 200
_MAX_DEPTH = 8


def _is_sensitive_key(key: Any) -> bool:
    return bool(_SENSITIVE_KEY_RE.search(str(key)))


def _json_safe(value: Any, depth: int = 0) -> Any:
    """Converts values into JSON-safe primitives and redacts sensitive keys."""
    if depth > _MAX_DEPTH:
        return "[TRUNCATED]"

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, bytes):
        return "[BINARY]"

    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]

    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                result["_truncated"] = True
                break
            safe_key = str(key)[:100]
            if _is_sensitive_key(key):
                result[safe_key] = _REDACTED
            else:
                result[safe_key] = _json_safe(item, depth + 1)
        return result

    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe(item, depth + 1)
            for item in list(value)[:_MAX_COLLECTION_ITEMS]
        ]

    return str(value)[:_MAX_STRING_LENGTH]


def sanitize(value: Any) -> Any:
    """Public sanitizer used by tests and callers that need a safe snapshot."""
    return _json_safe(value)


def _encode_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(sanitize(value), ensure_ascii=False, separators=(",", ":"))


def decode_json(value: Any) -> Any:
    """Decodes a MySQL JSON column value returned through SQLAlchemy text()."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return None


def mask_email(value: Optional[str]) -> Optional[str]:
    """Masks an email address while preserving enough context for audit review."""
    if not value:
        return None
    value = str(value).strip()
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(value: Optional[str]) -> Optional[str]:
    """Masks a phone number, keeping only the last four digits."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


def truncate_user_agent(value: Optional[str], limit: int = 512) -> Optional[str]:
    if not value:
        return None
    return str(value)[:limit]


# ---------------------------------------------------------------------------
# Actor snapshot
# ---------------------------------------------------------------------------

def actor_snapshot(
    actor: Optional[Dict[str, Any]] = None,
    *,
    actor_user_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_role: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Builds the immutable actor identity stored with an audit event.

    ``actor`` is the live profile dictionary returned by ``get_current_user``.
    The explicit keyword fallbacks exist for compatibility with service calls
    that only have an actor ID (for example older tests or CLI provisioning).
    """
    if actor:
        return {
            "user_id": actor.get("id"),
            "actor_name": actor.get("full_name"),
            "actor_role": actor.get("role"),
        }
    return {
        "user_id": actor_user_id,
        "actor_name": actor_name,
        "actor_role": actor_role,
    }


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------

def record_audit(
    conn: Connection,
    *,
    actor: Optional[Dict[str, Any]] = None,
    actor_user_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    actor_role: Optional[str] = None,
    action: str,
    module: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    description: Optional[str] = None,
    old_values: Any = None,
    new_values: Any = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Inserts one immutable audit row using the caller's transaction.

    Returns the generated audit UUID.  The caller must pass the same connection
    used for the related business mutation so both operations commit atomically.
    """
    snapshot = actor_snapshot(
        actor,
        actor_user_id=actor_user_id,
        actor_name=actor_name,
        actor_role=actor_role,
    )

    audit_id = str(uuid.uuid4())
    description_value = str(description)[:500] if description else None

    conn.execute(
        text(
            "INSERT INTO audit_logs "
            "(id, user_id, action, module, table_name, record_id, description, "
            " actor_name, actor_role, old_data, new_data, ip_address, user_agent) "
            "VALUES (:audit_id, :actor_id, :action, :module, :table_name, :record_id, "
            "        :description, :actor_name, :actor_role, :old_data, :new_data, "
            "        :ip_address, :user_agent)"
        ),
        {
            "audit_id": audit_id,
            "actor_id": snapshot["user_id"],
            "action": action,
            "module": module,
            "table_name": entity_type,
            "record_id": entity_id,
            "description": description_value,
            "actor_name": snapshot["actor_name"],
            "actor_role": snapshot["actor_role"],
            "old_data": _encode_json(old_values),
            "new_data": _encode_json(new_values),
            "ip_address": ip_address,
            "user_agent": truncate_user_agent(user_agent),
        },
    )
    return audit_id


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------

def _build_filters(
    *,
    search: str = "",
    module: str = "",
    action: str = "",
    entity_type: str = "",
    entity_id: str = "",
    user_id: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[str, Dict[str, Any]]:
    conditions: List[str] = []
    params: Dict[str, Any] = {}

    if search and search.strip():
        term = f"%{search.strip()[:100]}%"
        conditions.append(
            "(a.description LIKE :search OR a.actor_name LIKE :search "
            "OR a.action LIKE :search OR a.table_name LIKE :search "
            "OR a.record_id LIKE :search OR a.user_id LIKE :search)"
        )
        params["search"] = term

    if module and module.strip():
        conditions.append("a.module = :module")
        params["module"] = module.strip()

    if action and action.strip():
        conditions.append("a.action = :action")
        params["action"] = action.strip()

    if entity_type and entity_type.strip():
        conditions.append("a.table_name = :entity_type")
        params["entity_type"] = entity_type.strip()

    if entity_id and entity_id.strip():
        conditions.append("a.record_id = :entity_id")
        params["entity_id"] = entity_id.strip()

    if user_id and user_id.strip():
        conditions.append("a.user_id = :user_id")
        params["user_id"] = user_id.strip()

    if start_date:
        conditions.append("a.created_at >= :start_date")
        params["start_date"] = start_date

    if end_date:
        # Include the whole end date, not only midnight.
        conditions.append("a.created_at < DATE_ADD(:end_date, INTERVAL 1 DAY)")
        params["end_date"] = end_date

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


def _audit_stats(conn: Connection) -> Dict[str, int]:
    row = conn.execute(
        text(
            "SELECT COUNT(*) AS total, "
            "       COALESCE(SUM(created_at >= CURDATE()), 0) AS today, "
            "       COUNT(DISTINCT user_id) AS actors, "
            "       COUNT(DISTINCT module) AS modules "
            "FROM audit_logs"
        )
    ).mappings().first()
    if not row:
        return {"total": 0, "today": 0, "actors": 0, "modules": 0}
    return {
        "total": int(row.get("total") or 0),
        "today": int(row.get("today") or 0),
        "actors": int(row.get("actors") or 0),
        "modules": int(row.get("modules") or 0),
    }


def audit_log_list(
    engine: Engine,
    *,
    page: int = 1,
    limit: int = 25,
    search: str = "",
    module: str = "",
    action: str = "",
    entity_type: str = "",
    entity_id: str = "",
    user_id: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns a paginated, filtered audit-log list and global summary stats."""
    safe_page = max(1, int(page or 1))
    safe_limit = max(1, min(100, int(limit or 25)))
    offset = (safe_page - 1) * safe_limit
    where_clause, params = _build_filters(
        search=search,
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM audit_logs a {where_clause}"),
            params,
        ).scalar() or 0

        rows = conn.execute(
            text(
                "SELECT a.id, a.user_id, "
                "       COALESCE(a.actor_name, p.full_name, 'System') AS actor_name, "
                "       COALESCE(a.actor_role, p.role, 'system') AS actor_role, "
                "       a.action, a.module, a.table_name AS entity_type, "
                "       a.record_id AS entity_id, a.description, "
                "       a.ip_address, a.created_at "
                "FROM audit_logs a "
                "LEFT JOIN profiles p ON p.id = a.user_id "
                f"{where_clause} "
                "ORDER BY a.created_at DESC, a.id DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": safe_limit, "offset": offset},
        ).mappings().all()

        stats = _audit_stats(conn)

    total_int = int(total)
    total_pages = max(1, (total_int + safe_limit - 1) // safe_limit) if total_int > 0 else 0
    return {
        "logs": [dict(row) for row in rows],
        "total": total_int,
        "page": safe_page,
        "limit": safe_limit,
        "total_pages": total_pages,
        "stats": stats,
    }


def audit_log_get(engine: Engine, audit_id: str) -> Optional[Dict[str, Any]]:
    """Returns one audit row including JSON payloads, or ``None`` if missing."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT a.id, a.user_id, "
                "       COALESCE(a.actor_name, p.full_name, 'System') AS actor_name, "
                "       COALESCE(a.actor_role, p.role, 'system') AS actor_role, "
                "       a.action, a.module, a.table_name AS entity_type, "
                "       a.record_id AS entity_id, a.description, "
                "       a.old_data, a.new_data, a.ip_address, a.user_agent, "
                "       a.created_at "
                "FROM audit_logs a "
                "LEFT JOIN profiles p ON p.id = a.user_id "
                "WHERE a.id = :audit_id"
            ),
            {"audit_id": audit_id},
        ).mappings().first()

    if not row:
        return None

    result = dict(row)
    result["old_values"] = decode_json(result.pop("old_data", None))
    result["new_values"] = decode_json(result.pop("new_data", None))
    return result


def audit_log_options(engine: Engine) -> Dict[str, List[Any]]:
    """Returns distinct modules, actions, and actors for filter dropdowns."""
    with engine.connect() as conn:
        module_rows = conn.execute(
            text(
                "SELECT DISTINCT module FROM audit_logs "
                "WHERE module IS NOT NULL AND module <> '' ORDER BY module"
            )
        ).all()
        action_rows = conn.execute(
            text(
                "SELECT DISTINCT action FROM audit_logs "
                "WHERE action IS NOT NULL AND action <> '' ORDER BY action"
            )
        ).all()
        user_rows = conn.execute(
            text(
                "SELECT a.user_id AS id, "
                "       COALESCE(MAX(a.actor_name), MAX(p.full_name), 'System') AS name, "
                "       COALESCE(MAX(a.actor_role), MAX(p.role), 'system') AS role "
                "FROM audit_logs a "
                "LEFT JOIN profiles p ON p.id = a.user_id "
                "WHERE a.user_id IS NOT NULL "
                "GROUP BY a.user_id "
                "ORDER BY name"
            )
        ).mappings().all()

    modules = [row[0] for row in module_rows if row[0]]
    actions = [row[0] for row in action_rows if row[0]]
    users = [dict(row) for row in user_rows]
    return {
        "modules": modules or list(MODULES),
        "actions": actions,
        "users": users,
    }
