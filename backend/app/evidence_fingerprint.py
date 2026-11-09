"""Deterministic evidence and provenance snapshot fingerprints."""
import json


def evidence_fingerprint(db, case_id):
    """Hash current evidence and provenance, independent of row order."""
    import hashlib

    documents = [
        dict(row) for row in db.execute(
            """SELECT id, filename, source_note, sha256, passage_count
               FROM evidence_documents WHERE case_id=? ORDER BY id""",
            (case_id,)
        )
    ]
    passages = [
        dict(row) for row in db.execute(
            """SELECT p.id, p.document_id, p.position, p.content
               FROM evidence_passages p
               JOIN evidence_documents d ON d.id=p.document_id
               WHERE d.case_id=?
               ORDER BY p.document_id, p.position, p.id""",
            (case_id,)
        )
    ]

    provenance = []
    provenance_table_exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        ("source_provenance",),
    ).fetchone() is not None

    if provenance_table_exists:
        provenance = [
            dict(row) for row in db.execute(
                """SELECT sp.*
                   FROM source_provenance sp
                   JOIN evidence_documents d ON d.id=sp.document_id
                   WHERE d.case_id=? ORDER BY sp.document_id""",
                (case_id,)
            )
        ]

    payload = json.dumps(
        {"documents": documents, "passages": passages, "provenance": provenance},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
