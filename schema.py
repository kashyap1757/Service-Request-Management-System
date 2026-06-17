from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr


class Role(str, Enum):
    user = "user"
    staff = "staff"
    admin = "admin"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class RequestStatus(str, Enum):
    pending = "pending"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


# ---------- Users ----------

class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: Role = Role.user  # allows seeding staff/admin accounts; lock this down in production


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: Role

class AdminCreateUser(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: Role  # allows creating staff/admin accounts

# ---------- Categories ----------

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None


# ---------- Service Requests ----------

class ServiceRequestCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    priority: Priority = Priority.medium


class ServiceRequestUpdateStatus(BaseModel):
    status: RequestStatus
    note: Optional[str] = None


class ServiceRequestAssign(BaseModel):
    assigned_to: int  # user id of a staff/admin account


class ServiceRequestOut(BaseModel):
    id: int
    requester_id: int
    category_id: Optional[int]
    title: str
    description: Optional[str]
    priority: Priority
    status: RequestStatus
    assigned_to: Optional[int]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
