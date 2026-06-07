import json
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.document import (
    DocumentMetadata, DocumentResponse, DocumentListResponse, DocumentSearchParams
)
from app.models.document import DocumentType
from app.services.document_service import document_service
from app.core.security import get_current_user, require_roles, require_permission

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(..., description="Financial document file"),
    title: str = Form(...),
    company_name: str = Form(...),
    document_type: DocumentType = Form(...),
    description: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("admin", "analyst")),
):
    """
    Upload a financial document (PDF, DOCX, TXT, XLSX).
    Requires: admin or analyst role.
    """
    metadata = DocumentMetadata(
        title=title,
        company_name=company_name,
        document_type=document_type,
        description=description,
    )
    return await document_service.upload_document(db, file, metadata, current_user)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Retrieve all documents (paginated). Requires authentication."""
    result = document_service.get_all_documents(db, skip=skip, limit=limit)
    return result


@router.get("/search", response_model=DocumentListResponse)
def search_documents(
    title: Optional[str] = Query(default=None),
    company_name: Optional[str] = Query(default=None),
    document_type: Optional[DocumentType] = Query(default=None),
    uploaded_by: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Search documents by metadata fields. Requires authentication."""
    params = DocumentSearchParams(
        title=title,
        company_name=company_name,
        document_type=document_type,
        uploaded_by=uploaded_by,
    )
    result = document_service.search_by_metadata(db, params)
    return result


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Retrieve a single document by ID. Requires authentication."""
    return document_service.get_document_by_id(db, document_id)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Delete a document.
    Admins can delete any document; analysts can only delete their own.
    """
    return document_service.delete_document(db, document_id, current_user)
