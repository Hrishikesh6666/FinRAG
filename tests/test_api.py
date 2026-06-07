"""
Integration tests — require a running Postgres DB (use SQLite for CI).
Run: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.db.seed import seed

# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed(db)
    db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def admin_token(client):
    resp = client.post("/auth/login", json={
        "email": "admin@finrag.local",
        "password": "Admin@1234",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register(self, client):
        resp = client.post("/auth/register", json={
            "email": "analyst@finrag.local",
            "username": "analyst1",
            "password": "Analyst@1234",
            "full_name": "Jane Analyst",
        })
        assert resp.status_code == 201
        assert resp.json()["email"] == "analyst@finrag.local"

    def test_register_duplicate_email(self, client):
        client.post("/auth/register", json={
            "email": "dup@finrag.local",
            "username": "dup1",
            "password": "Dup@12345",
        })
        resp = client.post("/auth/register", json={
            "email": "dup@finrag.local",
            "username": "dup2",
            "password": "Dup@12345",
        })
        assert resp.status_code == 400

    def test_login_success(self, client):
        resp = client.post("/auth/login", json={
            "email": "admin@finrag.local",
            "password": "Admin@1234",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        resp = client.post("/auth/login", json={
            "email": "admin@finrag.local",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    def test_get_me(self, client, admin_token):
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_get_me_no_token(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 403


# ── Document tests ────────────────────────────────────────────────────────────

class TestDocuments:
    def test_list_documents_requires_auth(self, client):
        resp = client.get("/documents")
        assert resp.status_code == 403

    def test_list_documents_authenticated(self, client, admin_token):
        resp = client.get("/documents", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert "documents" in resp.json()

    def test_get_nonexistent_document(self, client, admin_token):
        resp = client.get("/documents/99999", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 404


# ── RBAC tests ────────────────────────────────────────────────────────────────

class TestRBAC:
    def test_list_roles_as_admin(self, client, admin_token):
        resp = client.get("/roles", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        role_names = [r["name"] for r in resp.json()]
        assert "admin" in role_names
        assert "analyst" in role_names

    def test_list_roles_unauthenticated(self, client):
        resp = client.get("/roles")
        assert resp.status_code == 403

    def test_create_role(self, client, admin_token):
        resp = client.post("/roles/create",
            json={"name": "viewer", "description": "Read-only access", "permissions": ["document:read"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "viewer"
