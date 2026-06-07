import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.document import Document, DocumentType
from app.models.user import User
from app.schemas.document import DocumentMetadata, DocumentResponse, DocumentSearchParams
from app.core.config import settings


class DocumentService:
    def __init__(self):
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _validate_file(self, file: UploadFile):
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in settings.allowed_extensions_list:
            raise HTTPException(
                status_code=400,
                detail=f"File type '.{ext}' not allowed. Allowed: {settings.allowed_extensions_list}",
            )

    def _doc_to_response(self, doc: Document, db: Session) -> DocumentResponse:
        uploader = db.query(User).filter(User.id == doc.uploaded_by).first()
        return DocumentResponse(
            document_id=doc.id,
            title=doc.title,
            company_name=doc.company_name,
            document_type=doc.document_type,
            description=doc.description,
            file_name=doc.file_name,
            file_size=doc.file_size,
            uploaded_by=uploader.username if uploader else str(doc.uploaded_by),
            is_indexed=doc.is_indexed,
            created_at=doc.created_at,
        )

    # ─── Upload ───────────────────────────────────────────────────────────────

    async def upload_document(
        self,
        db: Session,
        file: UploadFile,
        metadata: DocumentMetadata,
        current_user: User,
    ) -> DocumentResponse:
        self._validate_file(file)

        # Read content and check size
        content = await file.read()
        if len(content) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB} MB",
            )

        # Save file to disk with a UUID-safe name
        ext = file.filename.rsplit(".", 1)[-1].lower()
        safe_name = f"{uuid.uuid4().hex}.{ext}"
        file_path = self.upload_dir / safe_name

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        doc = Document(
            title=metadata.title,
            company_name=metadata.company_name,
            document_type=metadata.document_type,
            description=metadata.description,
            file_path=str(file_path),
            file_name=file.filename,
            file_size=len(content),
            mime_type=file.content_type,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return self._doc_to_response(doc, db)

    # ─── List / Get ───────────────────────────────────────────────────────────

    def get_all_documents(self, db: Session, skip: int = 0, limit: int = 50) -> dict:
        query = db.query(Document).filter(Document.is_active == True)
        total = query.count()
        docs = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        return {
            "total": total,
            "documents": [self._doc_to_response(d, db) for d in docs],
        }

    def get_document_by_id(self, db: Session, document_id: int) -> DocumentResponse:
        doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.is_active == True)
            .first()
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return self._doc_to_response(doc, db)

    def _get_doc_or_404(self, db: Session, document_id: int) -> Document:
        doc = db.query(Document).filter(Document.id == document_id, Document.is_active == True).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    # ─── Delete ───────────────────────────────────────────────────────────────

    def delete_document(self, db: Session, document_id: int, current_user: User) -> dict:
        doc = self._get_doc_or_404(db, document_id)

        user_role_names = {r.name for r in current_user.roles}
        if current_user.id != doc.uploaded_by and "admin" not in user_role_names:
            raise HTTPException(status_code=403, detail="Not authorized to delete this document")

        # Soft delete
        doc.is_active = False
        db.commit()

        # Remove physical file
        try:
            os.remove(doc.file_path)
        except FileNotFoundError:
            pass  # already gone, that's fine

        return {"message": f"Document {document_id} deleted successfully"}

    # ─── Metadata search ──────────────────────────────────────────────────────

    def search_by_metadata(self, db: Session, params: DocumentSearchParams) -> dict:
        query = db.query(Document).filter(Document.is_active == True)

        if params.title:
            query = query.filter(Document.title.ilike(f"%{params.title}%"))
        if params.company_name:
            query = query.filter(Document.company_name.ilike(f"%{params.company_name}%"))
        if params.document_type:
            query = query.filter(Document.document_type == params.document_type)
        if params.uploaded_by:
            user = db.query(User).filter(User.username == params.uploaded_by).first()
            if user:
                query = query.filter(Document.uploaded_by == user.id)
            else:
                return {"total": 0, "documents": []}

        docs = query.order_by(Document.created_at.desc()).all()
        return {
            "total": len(docs),
            "documents": [self._doc_to_response(d, db) for d in docs],
        }


document_service = DocumentService()
