from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class IndexDocumentResponse(BaseModel):
    document_id: int
    chunks_indexed: int
    message: str


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    top_k: Optional[int] = Field(default=5, ge=1, le=20)
    company_name: Optional[str] = None        
    document_type: Optional[str] = None       


class ChunkResult(BaseModel):
    document_id: int
    document_title: str
    company_name: str
    document_type: str
    chunk_text: str
    score: float                            
    vector_score: float                      
    chunk_index: int


class SemanticSearchResponse(BaseModel):
    query: str
    total_candidates: int                    
    results: List[ChunkResult]


class DocumentContextResponse(BaseModel):
    document_id: int
    title: str
    company_name: str
    chunks: List[Dict[str, Any]]
