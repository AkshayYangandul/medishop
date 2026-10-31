# MediShop — Medical Shop Management System

A pharmacy / medical shop management system for managing medicines, batches, inventory, customers, sales, invoices, expenses, and financial reports.

## Architecture

```
frontend/   React 19 + Vite + Tailwind CSS  →  Browser
backend/    Python FastAPI + SQLAlchemy   →  MySQL  (database name: medishop)
```

The intended data flow is:

**React (frontend) → Python (FastAPI) → MySQL**

The backend owns authentication, business logic, and database access. The frontend
never talks to the database directly and never stores passwords.

## Tech Stack

- **Frontend**: React 19, Vite 6, Tailwind CSS 3, react-hook-form + Zod, Recharts
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2, PyMySQL, Uvicorn
- **Database**: MySQL 8 (database name: `medishop`)
- **Auth**: PBKDF2-HMAC-SHA256 password hashing (FastAPI endpoint layer) + signed HS256 JWT (Bearer tokens)

## Roles

- **Admin** — user/role management, medicine & inventory, batches/stock/expiry/pricing, customers & sales, authorized invoice operations, expenses, full profit & financial reports, admin settings.
- **Pharmacist** — catalogue/batch/expiry/MRP view, customer creation, sales processing, invoice print/reprint, daily sales summaries. Cannot change roles, access restricted expense details, or view full financial reports.

All role restrictions are enforced server-side via FastAPI dependencies
(`require_active_admin`, `get_current_user`) and database operations — never only
in the UI.

## Getting Started

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then fill in real MySQL credentials and a strong AUTH_SECRET_KEY

# Run
uvicorn main:app --reload --port 8000
```

The API docs (Swagger UI) are available at: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

The Vite dev server should proxy `/api` requests to the backend (e.g. via
`server.proxy` in `vite.config.js`) so the frontend can call the same origin.

## Environment Variables

Backend (`backend/.env`):

| Variable | Purpose |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL connection |
| `DATABASE_URL` | Optional full connection URL override |
| `AUTH_SECRET_KEY` | JWT signing key (min 32 chars, required) |
| `TOKEN_EXPIRE_SECONDS` | JWT lifetime (default 3600) |

Frontend (e.g. `frontend/.env`): `VITE_API_URL=http://localhost:8000`

## Database

- Schema source of truth: `backend/schema.sql` (MySQL 8, InnoDB)
- Database name: `medishop`
- Live schema currently contains 14 tables (profiles, categories, brands, medicines, suppliers, purchases, batches, purchase_items, customers, invoices, invoice_items, expenses, stock_movements, audit_logs).

## Testing

Backend tests (offline unit tests; no DB required):

```bash
cd backend
python -m unittest discover -s . -p "test_*.py"
```

Live MySQL integration tests are opt-in and require a disposable test database:

```bash
RUN_LIVE_MYSQL_TESTS=1 TEST_DATABASE_URL=mysql+pymysql://... python -m unittest ...
```

Frontend:

```bash
cd frontend
npm run build
```

## Security Notes

- No secrets are committed. `.env` files are git-ignored; safe placeholders live in `.env.example`.
- Passwords are hashed with PBKDF2-HMAC-SHA256 (260,000 iterations, salted, constant-time verification).
- JWTs are signed HS256 with strict validation (signature, algorithm, expiry, `sub`, `exp`, clock-skew guard).
- Inactive accounts cannot authenticate; inactive admins cannot perform admin operations.
- Last active administrator protection is enforced server-side via a MySQL named lock (`medishop_admin_role_mutex`) with `SELECT ... FOR UPDATE`.
- Audit logs capture sensitive admin changes and never store credential material.
