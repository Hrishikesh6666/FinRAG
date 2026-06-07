from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.rag import (
    IndexDocumentResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    ChunkResult,
    DocumentContextResponse,
)
from app.services.rag_service import rag_service
from app.core.security import get_current_user, require_roles

router = APIRouter(prefix="/rag", tags=["RAG - Semantic Search"])


@router.post("/index-document", response_model=IndexDocumentResponse, status_code=201)
def index_document(
    document_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin", "analyst")),
):
    """
    Generate embeddings for a document and store in Qdrant.
    Requires: admin or analyst role.
    """
    try:
        result = rag_service.index_document(db, document_id)
        return IndexDocumentResponse(
            document_id=result["document_id"],
            chunks_indexed=result["chunks_indexed"],
            message=f"Successfully indexed {result['chunks_indexed']} chunks into Qdrant.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.delete("/remove-document/{document_id}")
def remove_document_vectors(
    document_id: int,
    _=Depends(require_roles("admin")),
):
    """
    Remove all vector embeddings for a document from Qdrant.
    Requires: admin role.
    """
    try:
        rag_service.remove_document(document_id)
        return {"message": f"Embeddings for document {document_id} removed from Qdrant."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Removal failed: {str(e)}")


@router.post("/search", response_model=SemanticSearchResponse)
def semantic_search(
    payload: SemanticSearchRequest,
    _=Depends(get_current_user),
):
    """
    Perform semantic search over indexed financial documents.
    
    Pipeline: Query → Embedding → Qdrant vector search (top 20) → CrossEncoder rerank → top 5
    
    Optional filters: company_name, document_type
    """
    try:
        result = rag_service.semantic_search(
            query=payload.query,
            top_k_rerank=payload.top_k,
            company_name=payload.company_name,
            document_type=payload.document_type,
        )

        chunks = [ChunkResult(**r) for r in result["results"]]
        return SemanticSearchResponse(
            query=result["query"],
            total_candidates=result["total_candidates"],
            results=chunks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/context/{document_id}", response_model=DocumentContextResponse)
def get_document_context(
    document_id: int,
    _=Depends(get_current_user),
):
    """
    Retrieve all stored chunks for a specific document from Qdrant.
    Useful for document-level context retrieval.
    """
    try:
        context = rag_service.get_document_context(document_id)
        return DocumentContextResponse(
            document_id=context["document_id"],
            title=context.get("title", ""),
            company_name=context.get("company_name", ""),
            chunks=context["chunks"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context retrieval failed: {str(e)}")
