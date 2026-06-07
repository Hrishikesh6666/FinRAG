from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.session import get_db
from app.schemas.role import RoleCreate, RoleResponse, AssignRoleRequest, UserRolesResponse
from app.services.role_service import role_service
from app.core.security import require_roles

router = APIRouter(tags=["Roles & Permissions"])


# ── Role management (admin only) ──────────────────────────────────────────────

@router.post("/roles/create", response_model=RoleResponse, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    """Create a new role with optional permissions. Admin only."""
    role = role_service.create_role(db, payload)
    return role_service.to_schema(role)


@router.get("/roles", response_model=List[RoleResponse])
def list_roles(
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    """List all roles. Admin only."""
    roles = role_service.list_roles(db)
    return [role_service.to_schema(r) for r in roles]


# ── User-Role assignment ──────────────────────────────────────────────────────

@router.post("/users/assign-role")
def assign_role(
    payload: AssignRoleRequest,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    """Assign a role to a user. Admin only."""
    return role_service.assign_role(db, payload)


@router.get("/users/{user_id}/roles", response_model=UserRolesResponse)
def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin")),
):
    """Get all roles assigned to a user. Admin only."""
    return role_service.get_user_roles(db, user_id)


@router.get("/users/{user_id}/permissions", response_model=List[str])
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    """Get all permissions for a user (derived from their roles). Admin only."""
    return role_service.get_user_permissions(db, user_id)
