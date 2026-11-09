"""Case-connected research discovery API."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException

from .research_pipeline import discover_case_research


router = APIRouter()
DB_PATH = None


@router.post("/api/cases/{case_id}/research/discover")
def discover_case_sources(case_id: str):
    """Return unverified research candidates for an existing case."""

    with sqlite3.connect(DB_PATH, timeout=20) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM cases WHERE id=?",
            (case_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(404, "Case not found")

    result = discover_case_research(dict(row))

    return {
        "case_id": case_id,
        "verification_status": "unverified",
        "queries": list(result.queries),
        "candidates": [
            {
                "title": item.title,
                "url": item.url,
                "description": item.description,
                "query": item.query,
                "verification_status": "unverified",
            }
            for item in result.candidates
        ],
        "errors": list(result.errors),
        "human_review_required": True,
        "evidence_imported": False,
    }


def install(app, db_path):
    global DB_PATH
    DB_PATH = str(db_path)
    app.include_router(router)
