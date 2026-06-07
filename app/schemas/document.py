from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.document import DocumentType


class DocumentMetadata(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    company_name: str = Field(..., min_length=1, max_length=255)
    document_type: DocumentType
    description: Optional[str] = None


class DocumentResponse(BaseModel):
    document_id: int
    title: str
    company_name: str
    document_type: DocumentType
    description: Optional[str]
    file_name: str
    file_size: Optional[int]
    uploaded_by: str          # username
    is_indexed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentResponse]


class DocumentSearchParams(BaseModel):
    title: Optional[str] = None
    company_name: Optional[str] = None
    document_type: Optional[DocumentType] = None
    uploaded_by: Optional[str] = None
