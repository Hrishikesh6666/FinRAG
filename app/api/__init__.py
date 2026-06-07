from fastapi import APIRouter
from app.api.routes import auth, documents, roles, rag

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(roles.router)
api_router.include_router(rag.router)
