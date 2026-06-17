# Service Request Management System — Backend

FastAPI backend for submitting, tracking, assigning, and resolving service/complaint
requests, with JWT authentication and role-based access control.

## Roles

- **user** — submits requests, views/tracks only their own requests.
- **staff** — views all requests, updates status, sees the org-wide dashboard.
- **admin** — everything staff can do, plus creating categories and assigning requests to staff.

Role is embedded in the JWT at login, so every protected route can authorize without
an extra DB lookup.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in DATABASE_URL and JWT_SECRET_KEY
uvicorn main:app --reload
```

Tables are created automatically on startup (`init_db()` in `database.py`).

## Data model

- `users` — id, full_name, email, password (bcrypt hash), role
- `categories` — id, name, description (e.g. Plumbing, Electrical, IT)
- `service_requests` — id, requester_id, category_id, title, description, priority,
  status, assigned_to, created_at, updated_at, resolved_at
- `request_status_history` — append-only audit trail of every status change

Status lifecycle: `pending → assigned → in_progress → resolved → closed`

## API overview

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/register` | public | create an account |
| POST | `/login` | public | get a JWT |
| POST | `/categories` | admin | create a request category |
| GET | `/categories` | any authenticated | list categories |
| POST | `/requests` | any authenticated | submit a new service request |
| GET | `/requests?status=` | any authenticated | list requests (own, for users; all, for staff/admin) |
| GET | `/requests/{id}` | any authenticated | request detail (owner or staff/admin) |
| PATCH | `/requests/{id}/status` | staff, admin | move a request through its lifecycle |
| PATCH | `/requests/{id}/assign` | admin | assign a request to a staff member |
| GET | `/dashboard/summary` | staff, admin | totals, status breakdown, avg. resolution time, staff workload |
| GET | `/dashboard/my-requests` | any authenticated | requester's own status breakdown |

## Notes / things to harden before production

- `/register` currently lets a caller set their own `role`. In production, restrict
  the `role` field so only an existing admin can create staff/admin accounts
  (e.g. drop `role` from `UserRegister` and add a separate admin-only endpoint).
- Add pagination to `GET /requests` once volume grows.
- Consider rate-limiting `/login` and `/register`.
