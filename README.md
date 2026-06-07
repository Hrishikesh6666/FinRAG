# FinRAG — Financial Document Management with Semantic RAG

A production-ready FastAPI application for storing, managing, and semantically searching financial documents using AI-powered RAG (Retrieval-Augmented Generation).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                  │
│                                                         │
│  /auth   /documents   /roles   /users   /rag            │
└──────────────┬──────────────────────────┬───────────────┘
               │                          │
     ┌─────────▼─────────┐    ┌──────────▼──────────┐
     │  PostgreSQL (SQL)  │    │   Qdrant (Vectors)  │
     │  - Users           │    │  - Document chunks  │
     │  - Roles/Perms     │    │  - Embeddings       │
     │  - Document meta   │    └─────────────────────┘
     └───────────────────┘
```

### RAG Pipeline

```
Document Upload
     │
     ▼
Text Extraction (PyPDF2 / python-docx / openpyxl)
     │
     ▼
Chunking via LangChain RecursiveCharacterTextSplitter
(chunk_size=512, overlap=64)
     │
     ▼
Embedding (OpenAI text-embedding-3-small, dim=1536)
     │
     ▼
Qdrant Upsert (with document metadata payload)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Semantic Search Query
     │
     ▼
Embed Query
     │
     ▼
Qdrant Vector Search → Top 20 candidates
     │
     ▼
CrossEncoder Rerank (cross-encoder/ms-marco-MiniLM-L-6-v2)
     │
     ▼
Top 5 Most Relevant Chunks returned
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.111 |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 |
| Vector DB | Qdrant 1.9 |
| Embeddings | OpenAI text-embedding-3-small |
| Chunking | LangChain RecursiveCharacterTextSplitter |
| Reranker | CrossEncoder ms-marco-MiniLM-L-6-v2 (local) |
| Auth | JWT (python-jose) + bcrypt |
| File parsing | PyPDF2, python-docx, openpyxl |

---

## Roles & Permissions

| Role | Permissions |
|------|-------------|
| **admin** | Full access to everything |
| **analyst** | Upload, read, edit, index documents + semantic search |
| **auditor** | Read documents + semantic search |
| **client** | Read documents only |

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY at minimum

# 2. Start all services
docker compose up --build

# API is live at http://localhost:8000
# Swagger UI: http://localhost:8000/docs
# Qdrant dashboard: http://localhost:6333/dashboard
```

### Option B — Local development

**Prerequisites**: Python 3.12+, PostgreSQL, Qdrant running locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in DATABASE_URL, QDRANT_URL, OPENAI_API_KEY

# 3. Run the app (tables + seed happen on startup)
uvicorn app.main:app --reload --port 8000
```

**Default admin login:**
- Email: `admin@finrag.local`
- Password: `Admin@1234`

---

## API Reference

### Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/register` | Register a new user | Public |
| POST | `/auth/login` | Get JWT token | Public |
| GET | `/auth/me` | Get current user profile | JWT |

**Login response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

All protected endpoints require: `Authorization: Bearer <token>`

---

### Documents

| Method | Endpoint | Description | Required Role |
|--------|----------|-------------|---------------|
| POST | `/documents/upload` | Upload a financial document | admin, analyst |
| GET | `/documents` | List all documents (paginated) | any auth |
| GET | `/documents/{id}` | Get document details | any auth |
| DELETE | `/documents/{id}` | Delete a document | admin (or own) |
| GET | `/documents/search` | Search by metadata | any auth |

**Upload example (multipart form):**
```
POST /documents/upload
Content-Type: multipart/form-data

file: <binary>
title: "Q4 2024 Financial Report"
company_name: "Acme Corp"
document_type: "report"
description: "Annual financial summary"
```

**Metadata search query params:** `title`, `company_name`, `document_type`, `uploaded_by`

---

### Roles & Permissions

| Method | Endpoint | Description | Required Role |
|--------|----------|-------------|---------------|
| POST | `/roles/create` | Create a new role | admin |
| GET | `/roles` | List all roles | admin |
| POST | `/users/assign-role` | Assign role to user | admin |
| GET | `/users/{id}/roles` | Get user's roles | admin |
| GET | `/users/{id}/permissions` | Get user's permissions | admin |

---

### RAG — Semantic Search

| Method | Endpoint | Description | Required Role |
|--------|----------|-------------|---------------|
| POST | `/rag/index-document?document_id=1` | Index document into Qdrant | admin, analyst |
| DELETE | `/rag/remove-document/{id}` | Remove vectors from Qdrant | admin |
| POST | `/rag/search` | Semantic search | any auth |
| GET | `/rag/context/{id}` | Get all chunks for a document | any auth |

**Semantic search request:**
```json
POST /rag/search
{
  "query": "financial risk related to high debt ratio",
  "top_k": 5,
  "company_name": "Acme Corp",
  "document_type": "report"
}
```

**Semantic search response:**
```json
{
  "query": "financial risk related to high debt ratio",
  "total_candidates": 20,
  "results": [
    {
      "document_id": 3,
      "document_title": "Q4 2024 Financial Report",
      "company_name": "Acme Corp",
      "document_type": "report",
      "chunk_text": "The company's debt-to-equity ratio stands at 2.4x...",
      "score": 0.923,
      "vector_score": 0.871,
      "chunk_index": 14
    }
  ]
}
```

---

## Project Structure

```
finrag/
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── auth.py          # /auth endpoints
│   │       ├── documents.py     # /documents endpoints
│   │       ├── roles.py         # /roles, /users endpoints
│   │       └── rag.py           # /rag endpoints
│   ├── core/
│   │   ├── config.py            # Pydantic settings
│   │   └── security.py          # JWT + RBAC dependencies
│   ├── db/
│   │   ├── session.py           # SQLAlchemy engine + Base
│   │   ├── init_db.py           # create_all()
│   │   └── seed.py              # Default roles + admin user
│   ├── models/
│   │   ├── user.py              # User ORM
│   │   ├── role.py              # Role + Permission ORM
│   │   └── document.py          # Document ORM
│   ├── schemas/
│   │   ├── auth.py              # Pydantic request/response models
│   │   ├── document.py
│   │   ├── role.py
│   │   └── rag.py
│   ├── services/
│   │   ├── auth_service.py      # Register, login logic
│   │   ├── document_service.py  # Upload, CRUD
│   │   ├── role_service.py      # RBAC operations
│   │   └── rag_service.py       # Embedding, Qdrant, reranking
│   ├── utils/
│   │   └── text_extractor.py    # PDF/DOCX/TXT/XLSX extraction
│   └── main.py                  # FastAPI app + lifespan
├── tests/
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Running Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

Tests use SQLite in-memory — no external DB needed.

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (required) | JWT signing key (min 32 chars) |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `OPENAI_API_KEY` | (required) | For OpenAI embeddings |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | HuggingFace reranker |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| `TOP_K_RETRIEVAL` | `20` | Candidates from Qdrant |
| `TOP_K_RERANK` | `5` | Final results after reranking |
| `MAX_FILE_SIZE_MB` | `50` | Upload size limit |
