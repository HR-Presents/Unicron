"""Authenticated, bounded research import into unverified evidence."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .evidence import MAX_BYTES, audit, chunk_text, extract_text, now
from .research_auth import require_research_auth
from .research_retrieval import ALLOWED_TYPES, RetrievalError
from .research_worker import retrieve_isolated


router = APIRouter(
    dependencies=[Depends(require_research_auth)]
)
DB_PATH = None
MAX_CONCURRENT_IMPORTS = 2
_import_slots = threading.BoundedSemaphore(MAX_CONCURRENT_IMPORTS)

EXTENSIONS = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
}


class ResearchImportRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2000)
    authority: str = Field(min_length=2, max_length=180)
    jurisdiction: str = Field(min_length=2, max_length=100)
    document_title: str = Field(min_length=3, max_length=250)
    source_type: str = Field(pattern="^(policy|benchmark|guidance|other)$")


@router.post(
    "/api/cases/{case_id}/research/import",
    status_code=201,
)
def import_research(case_id: str, request: ResearchImportRequest):
    """Retrieve a document and store it as unverified evidence."""

    with sqlite3.connect(DB_PATH, timeout=20) as con:
        exists = con.execute(
            "SELECT 1 FROM cases WHERE id=?",
            (case_id,),
        ).fetchone()

    if exists is None:
        raise HTTPException(404, "Case not found")

    if not _import_slots.acquire(blocking=False):
        raise HTTPException(
            429,
            "Research import capacity reached; retry later",
        )

    try:
        try:
            document = retrieve_isolated(request.url)
        except RetrievalError:
            raise HTTPException(
                422,
                "Research document retrieval failed",
            )
    finally:
        _import_slots.release()

    if document.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, "Unsupported research content type")

    if not document.payload or len(document.payload) > MAX_BYTES:
        raise HTTPException(413, "Invalid research document size")

    extension = EXTENSIONS[document.content_type]

    filename = (
        Path(urlsplit(request.url).path).stem[:100]
        or "research-document"
    ) + extension

    extracted = extract_text(filename, document.payload)
    chunks = chunk_text(extracted)

    digest = hashlib.sha256(document.payload).hexdigest()
    document_id = str(uuid4())
    stamp = now()

    with sqlite3.connect(DB_PATH, timeout=20) as con:
        con.execute("PRAGMA foreign_keys=ON")

        # Acquire the SQLite write lock before checking duplicates.
        # Concurrent imports serialize this check and insertion.
        con.execute("BEGIN IMMEDIATE")

        if con.execute(
            "SELECT 1 FROM cases WHERE id=?",
            (case_id,),
        ).fetchone() is None:
            raise HTTPException(404, "Case not found")

        duplicate = con.execute(
            """
            SELECT id FROM evidence_documents
            WHERE case_id=? AND sha256=?
            LIMIT 1
            """,
            (case_id, digest),
        ).fetchone()

        if duplicate:
            raise HTTPException(
                409,
                "Document content already exists in this case",
            )

        con.execute(
            "INSERT INTO evidence_documents VALUES (?,?,?,?,?,?,?)",
            (
                document_id,
                case_id,
                filename,
                "research import; unverified",
                digest,
                len(chunks),
                stamp,
            ),
        )

        con.executemany(
            "INSERT INTO evidence_passages VALUES (?,?,?,?,?)",
            [
                (str(uuid4()), document_id, index + 1, text, stamp)
                for index, text in enumerate(chunks)
            ],
        )

        con.execute(
            """
            INSERT INTO source_provenance
            (document_id,authority,jurisdiction,document_title,
             official_url,publication_date,effective_date,
             source_type,verification_status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                document_id,
                request.authority,
                request.jurisdiction,
                request.document_title,
                request.url,
                None,
                None,
                request.source_type,
                "unverified",
                stamp,
            ),
        )

        audit(
            con,
            case_id,
            "research.document_imported",
            f"document={document_id}; status=unverified",
        )

        con.commit()

    return {
        "id": document_id,
        "case_id": case_id,
        "filename": filename,
        "sha256": digest,
        "passage_count": len(chunks),
        "verification_status": "unverified",
        "human_review_required": True,
    }


def install(app, db_path):
    global DB_PATH
    DB_PATH = str(db_path)
    app.include_router(router)
