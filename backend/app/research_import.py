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

from .evidence import MAX_BYTES, audit, now
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



MAX_RESEARCH_PDF_PAGES = 200
MAX_RESEARCH_PDF_CHARS = 600_000
MAX_RESEARCH_PDF_CHUNKS = 1000


def extract_research_pdf(payload):
    """Extract bounded, page-labelled research evidence."""
    import io
    import re
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(payload), strict=False)
        page_count = len(reader.pages)
    except Exception:
        raise HTTPException(422, "Research PDF could not be parsed")

    if page_count > MAX_RESEARCH_PDF_PAGES:
        raise HTTPException(413, "Research PDF exceeds page limit")

    chunks = []
    total_chars = 0

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            raise HTTPException(
                422,
                f"PDF extraction failed on page {page_number}"
            )

        total_chars += len(text)

        if total_chars > MAX_RESEARCH_PDF_CHARS:
            raise HTTPException(
                413,
                "Research PDF exceeds extracted-text limit"
            )

        text = re.sub(r"[\t ]+", " ", text.replace("\x00", " "))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        if not text:
            continue

        start = 0

        while start < len(text):
            end = min(start + 850, len(text))

            if end < len(text):
                boundary = max(
                    text.rfind("\n", start + 500, end),
                    text.rfind(". ", start + 500, end),
                )

                if boundary > start + 500:
                    end = boundary + 1

            segment = text[start:end].strip()

            if segment:
                chunks.append(
                    f"[PDF page {page_number}]\n{segment}"
                )

            if len(chunks) > MAX_RESEARCH_PDF_CHUNKS:
                raise HTTPException(
                    413,
                    "Research PDF exceeds passage limit"
                )

            if end >= len(text):
                break

            start = max(start + 1, end - 100)

    if not chunks:
        raise HTTPException(422, "No extractable PDF text found")

    return chunks


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

    if extension == ".pdf":
        chunks = extract_research_pdf(document.payload)
    else:
        from .evidence import extract_text, chunk_text
        chunks = chunk_text(extract_text(filename, document.payload))

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
