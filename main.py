from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query

from database import init_db, get_db
from auth import hash_password, verify_password, create_token, get_current_user, require_role
from schema import (
    UserRegister, UserLogin, AdminCreateUser, UserOut,
    CategoryCreate, CategoryOut,
    ServiceRequestCreate, ServiceRequestUpdateStatus, ServiceRequestAssign, ServiceRequestOut,
    RequestStatus,
)

app = FastAPI(title="Service Request Management System")


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Auth ----------

@app.post("/register")
def register(user: UserRegister):
    hashed_password = hash_password(user.password)
    try:
        with get_db() as cur:
            cur.execute(
                "INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, %s) RETURNING id",
                (user.full_name, user.email, hashed_password, "user"),
            )
            new_id = cur.fetchone()[0]
            return {"message": "User registered successfully", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/users")
def create_staff_or_admin(user: AdminCreateUser, current_user: dict = Depends(require_role("admin"))):
    """Admin-only: create a staff or admin account. Self-service /register can't do this."""
    hashed_password = hash_password(user.password)
    try:
        with get_db() as cur:
            cur.execute(
                "INSERT INTO users (full_name, email, password, role) VALUES (%s, %s, %s, %s) RETURNING id",
                (user.full_name, user.email, hashed_password, user.role.value),
            )
            new_id = cur.fetchone()[0]
            return {"message": f"{user.role.value} account created successfully", "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/admin/users", response_model=List[UserOut])
def list_users(
    role: Optional[str] = Query(default=None, description="Filter by role: user, staff, or admin"),
    current_user: dict = Depends(require_role("admin")),
):
    """Admin-only: list every account, optionally filtered by role. Passwords are never returned."""
    with get_db() as cur:
        if role:
            cur.execute(
                "SELECT id, full_name, email, role FROM users WHERE role = %s ORDER BY id",
                (role,),
            )
        else:
            cur.execute("SELECT id, full_name, email, role FROM users ORDER BY id")
        rows = cur.fetchall()
        return [{"id": r[0], "full_name": r[1], "email": r[2], "role": r[3]} for r in rows]


@app.post("/login")
def login(user: UserLogin):
    with get_db() as cur:
        cur.execute("SELECT id, password, role FROM users WHERE email = %s", (user.email,))
        result = cur.fetchone()

        if not result:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_id, hashed_password, role = result

        if not verify_password(user.password, hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_token(user_id, role)
        return {"message": "Login successful", "token": token, "role": role}


# ---------- Categories ----------

@app.post("/categories")
def add_category(category: CategoryCreate, current_user: dict = Depends(require_role("admin"))):
    with get_db() as cur:
        cur.execute(
            "INSERT INTO categories (name, description) VALUES (%s, %s) RETURNING id",
            (category.name, category.description),
        )
        new_id = cur.fetchone()[0]
        return {"message": "Category added successfully", "id": new_id}


@app.get("/categories", response_model=List[CategoryOut])
def list_categories(current_user: dict = Depends(get_current_user)):
    with get_db() as cur:
        cur.execute("SELECT id, name, description FROM categories ORDER BY name")
        rows = cur.fetchall()
        return [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]


# ---------- Service Requests ----------

REQUEST_COLUMNS = """id, requester_id, category_id, title, description, priority,
                     status, assigned_to, created_at, updated_at, resolved_at"""


def _row_to_request(row) -> dict:
    return {
        "id": row[0],
        "requester_id": row[1],
        "category_id": row[2],
        "title": row[3],
        "description": row[4],
        "priority": row[5],
        "status": row[6],
        "assigned_to": row[7],
        "created_at": row[8],
        "updated_at": row[9],
        "resolved_at": row[10],
    }


@app.post("/requests")
def create_request(payload: ServiceRequestCreate, current_user: dict = Depends(get_current_user)):
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO service_requests (requester_id, category_id, title, description, priority)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (
                current_user["user_id"],
                payload.category_id,
                payload.title,
                payload.description,
                payload.priority.value,
            ),
        )
        new_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO request_status_history (request_id, status, changed_by) VALUES (%s, %s, %s)",
            (new_id, "pending", current_user["user_id"]),
        )
        return {"message": "Service request submitted successfully", "id": new_id}


@app.get("/requests", response_model=List[ServiceRequestOut])
def list_requests(
    status: Optional[RequestStatus] = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Regular users see only their own requests; staff/admin see everything."""
    with get_db() as cur:
        if current_user["role"] == "user":
            if status:
                cur.execute(
                    f"SELECT {REQUEST_COLUMNS} FROM service_requests "
                    "WHERE requester_id = %s AND status = %s ORDER BY created_at DESC",
                    (current_user["user_id"], status.value),
                )
            else:
                cur.execute(
                    f"SELECT {REQUEST_COLUMNS} FROM service_requests "
                    "WHERE requester_id = %s ORDER BY created_at DESC",
                    (current_user["user_id"],),
                )
        else:
            if status:
                cur.execute(
                    f"SELECT {REQUEST_COLUMNS} FROM service_requests "
                    "WHERE status = %s ORDER BY created_at DESC",
                    (status.value,),
                )
            else:
                cur.execute(f"SELECT {REQUEST_COLUMNS} FROM service_requests ORDER BY created_at DESC")

        rows = cur.fetchall()
        return [_row_to_request(r) for r in rows]


@app.get("/requests/{request_id}", response_model=ServiceRequestOut)
def get_request(request_id: int, current_user: dict = Depends(get_current_user)):
    with get_db() as cur:
        cur.execute(f"SELECT {REQUEST_COLUMNS} FROM service_requests WHERE id = %s", (request_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Service request not found")

        request_data = _row_to_request(row)
        if current_user["role"] == "user" and request_data["requester_id"] != current_user["user_id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this request")
        return request_data


@app.patch("/requests/{request_id}/status")
def update_status(
    request_id: int,
    payload: ServiceRequestUpdateStatus,
    current_user: dict = Depends(require_role("staff", "admin")),
):
    with get_db() as cur:
        cur.execute("SELECT id FROM service_requests WHERE id = %s", (request_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Service request not found")

        if payload.status == RequestStatus.resolved:
            cur.execute(
                "UPDATE service_requests SET status = %s, updated_at = NOW(), resolved_at = NOW() WHERE id = %s",
                (payload.status.value, request_id),
            )
        else:
            cur.execute(
                "UPDATE service_requests SET status = %s, updated_at = NOW() WHERE id = %s",
                (payload.status.value, request_id),
            )

        cur.execute(
            "INSERT INTO request_status_history (request_id, status, changed_by, note) VALUES (%s, %s, %s, %s)",
            (request_id, payload.status.value, current_user["user_id"], payload.note),
        )
        return {"message": "Status updated successfully"}


@app.patch("/requests/{request_id}/assign")
def assign_request(
    request_id: int,
    payload: ServiceRequestAssign,
    current_user: dict = Depends(require_role("admin")),
):
    with get_db() as cur:
        cur.execute("SELECT role FROM users WHERE id = %s", (payload.assigned_to,))
        staff_row = cur.fetchone()
        if not staff_row or staff_row[0] not in ("staff", "admin"):
            raise HTTPException(status_code=400, detail="Assignee must be a staff or admin user")

        cur.execute("SELECT id FROM service_requests WHERE id = %s", (request_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Service request not found")

        cur.execute(
            "UPDATE service_requests SET assigned_to = %s, status = 'assigned', updated_at = NOW() WHERE id = %s",
            (payload.assigned_to, request_id),
        )
        cur.execute(
            "INSERT INTO request_status_history (request_id, status, changed_by, note) VALUES (%s, %s, %s, %s)",
            (request_id, "assigned", current_user["user_id"], f"Assigned to user {payload.assigned_to}"),
        )
        return {"message": "Request assigned successfully"}


# ---------- Dashboards ----------

@app.get("/dashboard/summary")
def dashboard_summary(current_user: dict = Depends(require_role("staff", "admin"))):
    """Org-wide view: status breakdown, average resolution time, open workload per staff member."""
    with get_db() as cur:
        cur.execute("SELECT status, COUNT(*) FROM service_requests GROUP BY status")
        status_counts = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT COUNT(*) FROM service_requests")
        total = cur.fetchone()[0]

        cur.execute(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600)
            FROM service_requests WHERE resolved_at IS NOT NULL
            """
        )
        avg_resolution_hours = cur.fetchone()[0]

        cur.execute(
            """
            SELECT assigned_to, COUNT(*) FROM service_requests
            WHERE assigned_to IS NOT NULL AND status NOT IN ('resolved', 'closed')
            GROUP BY assigned_to
            """
        )
        workload = {row[0]: row[1] for row in cur.fetchall()}

        return {
            "total_requests": total,
            "status_breakdown": status_counts,
            "average_resolution_time_hours": round(avg_resolution_hours, 2) if avg_resolution_hours else None,
            "open_workload_by_staff": workload,
        }


@app.get("/dashboard/my-requests")
def my_dashboard(current_user: dict = Depends(get_current_user)):
    """Personal view for any user: their own request counts by status."""
    with get_db() as cur:
        cur.execute(
            "SELECT status, COUNT(*) FROM service_requests WHERE requester_id = %s GROUP BY status",
            (current_user["user_id"],),
        )
        status_counts = {row[0]: row[1] for row in cur.fetchall()}
        return {"status_breakdown": status_counts}