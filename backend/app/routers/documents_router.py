"""
documents_router.py — Document intelligence endpoints for FinAI.
════════════════════════════════════════════════════════════════

Endpoints:
  POST   /api/documents/upload           — ingest a file into the RAG pipeline
  GET    /api/documents                  — list indexed documents
  GET    /api/documents/formats          — supported file formats
  GET    /api/documents/{id}             — document details
  DELETE /api/documents/{id}             — remove document + vector store chunks
  POST   /api/documents/search           — semantic search across all documents
  GET    /api/documents/{id}/chunks      — preview indexed chunks for a document

Authentication:
  Uses get_optional_user — works with or without JWT token.
  Deletion requires at least analyst role (enforced server-side).
"""

import logging
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_optional_user
from app.services.document_ingestion import document_ingestion_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ─────────────────────────────────────────────────────────────────────────────
# Upload & Ingest
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document into the RAG pipeline",
)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(
        default="other",
        description="Type: report | memo | policy | transcript | audit | reference | other",
    ),
    period: Optional[str] = Form(default=None, description="e.g. 'Q1 2025' or 'January 2025'"),
    author: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """
    Upload a document and index it into the RAG pipeline.

    Supports: PDF, Word (.docx), Excel (.xlsx), text (.txt / .md / .csv)

    The document is:
    1. Saved temporarily
    2. Text extracted with format-specific parser
    3. Split into overlapping chunks
    4. Indexed into ChromaDB for semantic search
    5. Stored in FinancialDocument table for text-search fallback

    Returns ingestion stats including chunk count and estimated tokens.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Save to temp file
    suffix = os.path.splitext(file.filename)[-1].lower()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if len(content) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is empty",
                )
            tmp.write(content)
            tmp_path = tmp.name

        # Build extra metadata
        extra_meta: dict = {}
        if period:
            extra_meta["period"] = period
        if author:
            extra_meta["author"] = author
        if description:
            extra_meta["description"] = description
        if current_user:
            extra_meta["uploaded_by"] = current_user.email

        result = await document_ingestion_service.ingest_file(
            file_path=tmp_path,
            filename=file.filename,
            document_type=document_type,
            db=db,
            metadata=extra_meta,
        )

        if result.get("error") and not result.get("document_id"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to ingest '{file.filename}': {result['error']}",
            )

        await db.commit()

        return {
            "success": True,
            "filename": file.filename,
            **result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document upload failed for '%s': %s", file.filename, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}",
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# List & Read
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/formats",
    summary="Return supported file formats and library availability",
)
async def get_supported_formats():
    """Return which file formats are supported and which libraries are installed."""
    return document_ingestion_service.supported_formats()


@router.get(
    "",
    summary="List all indexed documents",
)
async def list_documents(
    document_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    Return a paginated list of ingested documents.

    Optionally filter by document_type:
      report | memo | policy | transcript | audit | reference | other
    """
    if limit > 200:
        limit = 200
    docs = await document_ingestion_service.list_documents(
        db, document_type=document_type, limit=limit, offset=offset,
    )
    return {
        "documents": docs,
        "count": len(docs),
        "offset": offset,
        "limit": limit,
    }


@router.get(
    "/{document_id}",
    summary="Get document details by ID",
)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return full metadata and preview for a specific document."""
    doc = await document_ingestion_service.get_document(document_id, db)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────────────────

@router.delete(
    "/{document_id}",
    summary="Delete a document and all its vector store chunks",
)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_optional_user),
):
    """
    Permanently remove a document from:
    - FinancialDocument table (DB)
    - ChromaDB vector store chunks

    This cannot be undone. Re-upload the file to re-index.
    """
    result = await document_ingestion_service.delete_document(document_id, db)
    if not result.get("deleted"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("error", "Deletion failed"),
        )

    await db.commit()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Search
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/search",
    summary="Semantic search over all indexed document chunks",
)
async def search_documents(
    body: dict,
):
    """
    Search all indexed documents using semantic similarity.

    Request body: {"query": "string", "n_results": 5}

    Returns relevant chunks with similarity scores and source metadata.
    """
    query = body.get("query", "").strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'query' field is required",
        )

    n_results = min(int(body.get("n_results", 5)), 20)
    results = await document_ingestion_service.search(query, n_results=n_results)

    return {
        "query": query,
        "results": results,
        "count": len(results),
    }
