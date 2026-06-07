import enum
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class DocumentType(str, enum.Enum):
    invoice = "invoice"
    report = "report"
    contract = "contract"
    agreement = "agreement"
    other = "other"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    company_name = Column(String(255), nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    description = Column(Text, nullable=True)

    # File storage
    file_path = Column(String(1000), nullable=False)     # path on disk
    file_name = Column(String(500), nullable=False)      # original filename
    file_size = Column(Integer, nullable=True)            # bytes
    mime_type = Column(String(100), nullable=True)

    # Flags
    is_indexed = Column(Boolean, default=False)          # True once in Qdrant
    is_active = Column(Boolean, default=True)

    # Ownership
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    uploaded_by_user = relationship("User", back_populates="documents")
