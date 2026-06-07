"""
RAG Service
-----------
Pipeline:
  Document → Text Extraction → Chunking → Embeddings → Qdrant
  Query → Embedding → Vector Search (top 20) → CrossEncoder Rerank → top 5
"""
import logging
import uuid
from typing import List, Dict, Any, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.utils.text_extractor import extract_text

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Lazy-loaded embedding provider — uses OpenAI by default."""

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            from langchain_openai import OpenAIEmbeddings
            self._model = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
            )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._load()
        return self._model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        self._load()
        return self._model.embed_query(text)


class RerankerProvider:
    """Lazy-loaded CrossEncoder reranker (runs locally via sentence-transformers)."""

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(settings.RERANKER_MODEL)

    def rerank(self, query: str, passages: List[str]) -> List[float]:
        """Return a score per passage (higher = more relevant)."""
        self._load()
        pairs = [[query, p] for p in passages]
        scores = self._model.predict(pairs)
        return scores.tolist()


class RAGService:
    def __init__(self):
        self.embedder = EmbeddingProvider()
        self.reranker = RerankerProvider()
        self._qdrant: Optional[QdrantClient] = None
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    # ─── Qdrant client ────────────────────────────────────────────────────────

    @property
    def qdrant(self) -> QdrantClient:
        if self._qdrant is None:
            kwargs = {"url": settings.QDRANT_URL}
            if settings.QDRANT_API_KEY:
                kwargs["api_key"] = settings.QDRANT_API_KEY
            self._qdrant = QdrantClient(**kwargs)
            self._ensure_collection()
        return self._qdrant

    def _ensure_collection(self):
        collections = [c.name for c in self.qdrant.get_collections().collections]
        if settings.QDRANT_COLLECTION_NAME not in collections:
            self.qdrant.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {settings.QDRANT_COLLECTION_NAME}")

    # ─── Indexing ─────────────────────────────────────────────────────────────

    def index_document(self, db: Session, document_id: int) -> Dict[str, Any]:
        doc: Document = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # 1. Extract text
        raw_text = extract_text(doc.file_path)
        if not raw_text.strip():
            raise ValueError("No text could be extracted from the document")

        # 2. Chunk
        chunks = self._splitter.split_text(raw_text)
        logger.info(f"Document {document_id} split into {len(chunks)} chunks")

        # 3. Embed
        embeddings = self.embedder.embed_documents(chunks)

        # 4. Build Qdrant points
        points = []
        for idx, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid4())
            payload = {
                "document_id": document_id,
                "document_title": doc.title,
                "company_name": doc.company_name,
                "document_type": doc.document_type.value,
                "chunk_index": idx,
                "chunk_text": chunk,
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        # 5. Upsert to Qdrant (batch of 100)
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=points[i : i + batch_size],
            )

        # 6. Mark document as indexed
        doc.is_indexed = True
        db.commit()

        return {"document_id": document_id, "chunks_indexed": len(chunks)}

    # ─── Remove document vectors ──────────────────────────────────────────────

    def remove_document(self, document_id: int) -> int:
        """Delete all vectors belonging to this document. Returns deleted count."""
        result = self.qdrant.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id),
                    )
                ]
            ),
        )
        logger.info(f"Removed vectors for document {document_id}")
        return result

    # ─── Semantic search with reranking ───────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        top_k_retrieve: int = None,
        top_k_rerank: int = None,
        company_name: Optional[str] = None,
        document_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        top_k_retrieve = top_k_retrieve or settings.TOP_K_RETRIEVAL
        top_k_rerank = top_k_rerank or settings.TOP_K_RERANK

        # 1. Embed query
        query_vector = self.embedder.embed_query(query)

        # 2. Optional metadata filter
        must_conditions = []
        if company_name:
            must_conditions.append(
                FieldCondition(key="company_name", match=MatchValue(value=company_name))
            )
        if document_type:
            must_conditions.append(
                FieldCondition(key="document_type", match=MatchValue(value=document_type))
            )

        search_filter = Filter(must=must_conditions) if must_conditions else None

        # 3. Vector search — retrieve top_k_retrieve candidates
        hits = self.qdrant.search(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            query_vector=query_vector,
            limit=top_k_retrieve,
            query_filter=search_filter,
            with_payload=True,
        )

        if not hits:
            return {"query": query, "total_candidates": 0, "results": []}

        # 4. Rerank
        passages = [h.payload["chunk_text"] for h in hits]
        rerank_scores = self.reranker.rerank(query, passages)

        # 5. Sort by reranker score, keep top_k_rerank
        ranked = sorted(
            zip(hits, rerank_scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k_rerank]

        results = [
            {
                "document_id": hit.payload["document_id"],
                "document_title": hit.payload["document_title"],
                "company_name": hit.payload["company_name"],
                "document_type": hit.payload["document_type"],
                "chunk_text": hit.payload["chunk_text"],
                "score": float(score),
                "vector_score": float(hit.score),
                "chunk_index": hit.payload["chunk_index"],
            }
            for hit, score in ranked
        ]

        return {
            "query": query,
            "total_candidates": len(hits),
            "results": results,
        }

    # ─── Context retrieval for a specific document ────────────────────────────

    def get_document_context(self, document_id: int) -> Dict[str, Any]:
        """Fetch all stored chunks for a document from Qdrant."""
        results, _ = self.qdrant.scroll(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id))
                ]
            ),
            limit=500,
            with_payload=True,
            with_vectors=False,
        )

        if not results:
            return {"document_id": document_id, "chunks": []}

        chunks = sorted(
            [
                {
                    "chunk_index": r.payload["chunk_index"],
                    "chunk_text": r.payload["chunk_text"],
                }
                for r in results
            ],
            key=lambda x: x["chunk_index"],
        )

        first = results[0].payload
        return {
            "document_id": document_id,
            "title": first.get("document_title", ""),
            "company_name": first.get("company_name", ""),
            "chunks": chunks,
        }


rag_service = RAGService()
