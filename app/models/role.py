from sqlalchemy import Column, Integer, String, Table, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.session import Base

# ── many-to-many: roles ↔ permissions ────────────────────────────────────────
role_permission_table = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# ── many-to-many: users ↔ roles ───────────────────────────────────────────────
user_role_table = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)   # e.g. "document:upload"
    description = Column(Text, nullable=True)

    roles = relationship("Role", secondary=role_permission_table, back_populates="permissions")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)   # admin | analyst | auditor | client
    description = Column(Text, nullable=True)

    permissions = relationship("Permission", secondary=role_permission_table, back_populates="roles")
    users = relationship("User", secondary=user_role_table, back_populates="roles")
