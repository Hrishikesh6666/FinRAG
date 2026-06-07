from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.role import Role, Permission
from app.models.user import User
from app.schemas.role import RoleCreate, AssignRoleRequest, RoleResponse, UserRolesResponse


class RoleService:
    # ─── Roles ────────────────────────────────────────────────────────────────

    def create_role(self, db: Session, payload: RoleCreate) -> Role:
        if db.query(Role).filter(Role.name == payload.name).first():
            raise HTTPException(status_code=400, detail=f"Role '{payload.name}' already exists")

        role = Role(name=payload.name, description=payload.description)

        # Attach permissions (create if they don't exist)
        for perm_name in payload.permissions:
            perm = db.query(Permission).filter(Permission.name == perm_name).first()
            if not perm:
                perm = Permission(name=perm_name)
                db.add(perm)
            role.permissions.append(perm)

        db.add(role)
        db.commit()
        db.refresh(role)
        return role

    def list_roles(self, db: Session) -> list[Role]:
        return db.query(Role).all()

    def get_role(self, db: Session, role_name: str) -> Role:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role '{role_name}' not found")
        return role

    # ─── User-Role assignment ─────────────────────────────────────────────────

    def assign_role(self, db: Session, payload: AssignRoleRequest) -> dict:
        user = db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        role = db.query(Role).filter(Role.name == payload.role_name).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role '{payload.role_name}' not found")

        if role in user.roles:
            raise HTTPException(status_code=400, detail="User already has this role")

        user.roles.append(role)
        db.commit()
        return {"message": f"Role '{role.name}' assigned to user '{user.username}'"}

    def get_user_roles(self, db: Session, user_id: int) -> UserRolesResponse:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        roles = [r.name for r in user.roles]
        permissions = list({p.name for r in user.roles for p in r.permissions})

        return UserRolesResponse(
            user_id=user.id,
            username=user.username,
            roles=roles,
            permissions=permissions,
        )

    def get_user_permissions(self, db: Session, user_id: int) -> list[str]:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return list({p.name for r in user.roles for p in r.permissions})

    # ─── Schema helper ────────────────────────────────────────────────────────

    @staticmethod
    def to_schema(role: Role) -> RoleResponse:
        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=[p.name for p in role.permissions],
        )


role_service = RoleService()
