"""
Seed the database with default roles, permissions, and an admin user.
Run once: python -m app.db.seed
Or it is called automatically on app startup if DB is empty.
"""
import logging
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.init_db import init_db
from app.models.role import Role, Permission
from app.models.user import User
from app.core.security import hash_password

logger = logging.getLogger(__name__)

# ── Default permission set ────────────────────────────────────────────────────
DEFAULT_PERMISSIONS = [
    ("document:upload", "Upload financial documents"),
    ("document:read", "View documents"),
    ("document:edit", "Edit document metadata"),
    ("document:delete", "Delete documents"),
    ("document:index", "Trigger RAG indexing"),
    ("rag:search", "Perform semantic search"),
    ("user:manage", "Manage users and roles"),
    ("role:manage", "Create and assign roles"),
]

# ── Role → permissions mapping ────────────────────────────────────────────────
DEFAULT_ROLES = {
    "admin": [p[0] for p in DEFAULT_PERMISSIONS],   # full access
    "analyst": ["document:upload", "document:read", "document:edit", "document:index", "rag:search"],
    "auditor": ["document:read", "rag:search"],
    "client": ["document:read"],
}

ADMIN_EMAIL = "admin@finrag.local"
ADMIN_PASSWORD = "Admin@1234"   # CHANGE in production


def seed(db: Session):
    # 1. Permissions
    perm_map: dict[str, Permission] = {}
    for name, desc in DEFAULT_PERMISSIONS:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, description=desc)
            db.add(perm)
        perm_map[name] = perm
    db.flush()

    # 2. Roles
    role_map: dict[str, Role] = {}
    for role_name, perm_names in DEFAULT_ROLES.items():
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name)
            db.add(role)
        role.permissions = [perm_map[p] for p in perm_names]
        role_map[role_name] = role
    db.flush()

    # 3. Default admin user
    admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if not admin:
        admin = User(
            email=ADMIN_EMAIL,
            username="admin",
            hashed_password=hash_password(ADMIN_PASSWORD),
            full_name="System Administrator",
        )
        db.add(admin)
        db.flush()
        admin.roles = [role_map["admin"]]
        logger.info(f"Created default admin user: {ADMIN_EMAIL}")

    db.commit()
    logger.info("Database seeded successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
