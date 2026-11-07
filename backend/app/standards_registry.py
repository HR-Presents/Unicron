"""Case-scoped standards traceability with evidence and human-review gates."""
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
DB_PATH = None


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


class Framework(BaseModel):
    identifier: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=250)
    publisher: str = Field(min_length=2, max_length=180)
    edition: str = Field(min_length=1, max_length=100)
    official_url: str = Field(min_length=10, max_length=1000)
    normative_status: str = Field(
        pattern="^(voluntary|guidance|regulatory|unknown)$"
    )


def install(app, db_path):
    global DB_PATH
    DB_PATH = str(db_path)

    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS standards_frameworks (
            identifier TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            publisher TEXT NOT NULL,
            edition TEXT NOT NULL,
            official_url TEXT NOT NULL,
            normative_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS standards_requirements (
            id TEXT PRIMARY KEY,
            framework_id TEXT NOT NULL
                REFERENCES standards_frameworks(identifier),
            requirement_code TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(framework_id, requirement_code)
        );

        CREATE TABLE IF NOT EXISTS standards_mappings (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL REFERENCES cases(id),
            requirement_id TEXT NOT NULL
                REFERENCES standards_requirements(id),
            passage_id TEXT NOT NULL
                REFERENCES evidence_passages(id),
            assessment TEXT NOT NULL,
            rationale TEXT NOT NULL,
            review_status TEXT NOT NULL DEFAULT 'pending'
                CHECK(review_status IN ('pending','verified','rejected')),
            reviewed_by TEXT,
            review_rationale TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(case_id, requirement_id, passage_id)
        );

        CREATE INDEX IF NOT EXISTS idx_standards_mapping_case
            ON standards_mappings(case_id);

        CREATE INDEX IF NOT EXISTS idx_standards_mapping_requirement
            ON standards_mappings(requirement_id);

        CREATE INDEX IF NOT EXISTS idx_standards_mapping_passage
            ON standards_mappings(passage_id);
        """)


    register_routes(app)

# Framework and requirement registration.
# Reviewer authentication is shared with the existing provenance registry.
from uuid import uuid4
from urllib.parse import urlparse
from fastapi import Header
from .source_registry import require_reviewer


class Requirement(BaseModel):
    framework_id: str = Field(min_length=2, max_length=100)
    requirement_code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=5, max_length=2000)


def validate_official_url(url):
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise HTTPException(
            status_code=422,
            detail="Official URL must be HTTPS without embedded credentials",
        )


@router.post("/api/standards/frameworks", status_code=201)
def create_framework(
    payload: Framework,
    x_reviewer_key: str | None = Header(default=None),
):
    require_reviewer(x_reviewer_key)
    validate_official_url(payload.official_url)

    with connect() as db:
        if db.execute(
            "SELECT 1 FROM standards_frameworks WHERE identifier=?",
            (payload.identifier,),
        ).fetchone():
            raise HTTPException(409, "Framework already exists")

        db.execute(
            """INSERT INTO standards_frameworks
               (identifier,title,publisher,edition,official_url,
                normative_status,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                payload.identifier,
                payload.title,
                payload.publisher,
                payload.edition,
                payload.official_url,
                payload.normative_status,
                now(),
            ),
        )
        db.commit()
        return dict(
            db.execute(
                "SELECT * FROM standards_frameworks WHERE identifier=?",
                (payload.identifier,),
            ).fetchone()
        )


@router.get("/api/standards/frameworks")
def list_frameworks():
    with connect() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT * FROM standards_frameworks ORDER BY identifier"
            )
        ]


@router.post("/api/standards/requirements", status_code=201)
def create_requirement(
    payload: Requirement,
    x_reviewer_key: str | None = Header(default=None),
):
    require_reviewer(x_reviewer_key)

    with connect() as db:
        framework = db.execute(
            "SELECT 1 FROM standards_frameworks WHERE identifier=?",
            (payload.framework_id,),
        ).fetchone()

        if not framework:
            raise HTTPException(404, "Framework not found")

        existing = db.execute(
            """SELECT 1 FROM standards_requirements
               WHERE framework_id=? AND requirement_code=?""",
            (payload.framework_id, payload.requirement_code),
        ).fetchone()

        if existing:
            raise HTTPException(409, "Requirement already exists")

        requirement_id = str(uuid4())

        db.execute(
            """INSERT INTO standards_requirements
               (id,framework_id,requirement_code,description,created_at)
               VALUES (?,?,?,?,?)""",
            (
                requirement_id,
                payload.framework_id,
                payload.requirement_code,
                payload.description,
                now(),
            ),
        )
        db.commit()

        return dict(
            db.execute(
                "SELECT * FROM standards_requirements WHERE id=?",
                (requirement_id,),
            ).fetchone()
        )


@router.get("/api/standards/requirements")
def list_requirements():
    with connect() as db:
        return [
            dict(row)
            for row in db.execute(
                """SELECT * FROM standards_requirements
                   ORDER BY framework_id, requirement_code"""
            )
        ]

# Case-scoped evidence mapping and immutable review.

class MappingCreate(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=100)
    passage_id: str = Field(min_length=1, max_length=100)
    assessment: str = Field(
        pattern="^(potential_alignment|potential_gap|needs_review)$"
    )
    rationale: str = Field(min_length=20, max_length=4000)


class MappingDecision(BaseModel):
    decision: str = Field(pattern="^(verified|rejected)$")
    reviewer: str = Field(min_length=2, max_length=180)
    rationale: str = Field(min_length=20, max_length=4000)


def write_audit(db, case_id, action, detail):
    db.execute(
        """INSERT INTO audit (id,case_id,action,detail,created_at)
           VALUES (?,?,?,?,?)""",
        (str(uuid4()), case_id, action, detail, now()),
    )


def require_case(db, case_id):
    if not db.execute(
        "SELECT 1 FROM cases WHERE id=?", (case_id,)
    ).fetchone():
        raise HTTPException(404, "Case not found")


@router.post("/api/cases/{case_id}/standards/mappings", status_code=201)
def create_mapping(
    case_id: str,
    payload: MappingCreate,
    x_reviewer_key: str | None = Header(default=None),
):
    require_reviewer(x_reviewer_key)

    with connect() as db:
        require_case(db, case_id)

        requirement = db.execute(
            "SELECT id FROM standards_requirements WHERE id=?",
            (payload.requirement_id,),
        ).fetchone()

        if not requirement:
            raise HTTPException(404, "Requirement not found")

        passage = db.execute(
            """SELECT p.id, d.id AS document_id
               FROM evidence_passages p
               JOIN evidence_documents d ON d.id=p.document_id
               WHERE p.id=? AND d.case_id=?""",
            (payload.passage_id, case_id),
        ).fetchone()

        if not passage:
            raise HTTPException(
                422, "Evidence passage does not belong to this case"
            )

        source = db.execute(
            """SELECT verification_status
               FROM source_provenance WHERE document_id=?""",
            (passage["document_id"],),
        ).fetchone()

        if not source or source["verification_status"] != "verified":
            raise HTTPException(
                422, "Mapping requires reviewer-verified source provenance"
            )

        existing = db.execute(
            """SELECT 1 FROM standards_mappings
               WHERE case_id=? AND requirement_id=? AND passage_id=?""",
            (case_id, payload.requirement_id, payload.passage_id),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Evidence mapping already exists",
            )

        mapping_id = str(uuid4())

        try:
            db.execute(
                """INSERT INTO standards_mappings
                   (id,case_id,requirement_id,passage_id,
                    assessment,rationale,review_status,created_at)
                   VALUES (?,?,?,?,?,?,'pending',?)""",
                (
                    mapping_id,
                    case_id,
                    payload.requirement_id,
                    payload.passage_id,
                    payload.assessment,
                    payload.rationale,
                    now(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Mapping conflicts with an existing record",
            ) from exc

        write_audit(
            db, case_id, "standards.mapping_created",
            f"mapping={mapping_id}; status=pending",
        )

        db.commit()
        return dict(db.execute(
            "SELECT * FROM standards_mappings WHERE id=?",
            (mapping_id,),
        ).fetchone())


@router.get("/api/cases/{case_id}/standards/mappings")
def list_mappings(case_id: str):
    with connect() as db:
        require_case(db, case_id)
        return [
            dict(row) for row in db.execute(
                """SELECT m.*, r.framework_id, r.requirement_code
                   FROM standards_mappings m
                   JOIN standards_requirements r
                     ON r.id=m.requirement_id
                   WHERE m.case_id=?
                   ORDER BY m.created_at DESC, m.id DESC""",
                (case_id,),
            )
        ]


@router.post(
    "/api/cases/{case_id}/standards/mappings/{mapping_id}/review",
    status_code=201,
)
def review_mapping(
    case_id: str,
    mapping_id: str,
    payload: MappingDecision,
    x_reviewer_key: str | None = Header(default=None),
):
    require_reviewer(x_reviewer_key)

    with connect() as db:
        require_case(db, case_id)

        mapping = db.execute(
            """SELECT m.*, p.document_id
               FROM standards_mappings m
               JOIN evidence_passages p ON p.id=m.passage_id
               WHERE m.id=? AND m.case_id=?""",
            (mapping_id, case_id),
        ).fetchone()

        if not mapping:
            raise HTTPException(404, "Mapping not found")

        if mapping["review_status"] != "pending":
            raise HTTPException(409, "Mapping review is immutable")

        if payload.decision == "verified":
            source = db.execute(
                """SELECT verification_status
                   FROM source_provenance WHERE document_id=?""",
                (mapping["document_id"],),
            ).fetchone()

            if not source or source["verification_status"] != "verified":
                raise HTTPException(
                    422, "Verified source provenance required"
                )

        db.execute(
            """UPDATE standards_mappings
               SET review_status=?, reviewed_by=?,
                   review_rationale=?, reviewed_at=?
               WHERE id=? AND case_id=? AND review_status='pending'""",
            (
                payload.decision,
                payload.reviewer,
                payload.rationale,
                now(),
                mapping_id,
                case_id,
            ),
        )

        write_audit(
            db, case_id, "standards.mapping_reviewed",
            f"mapping={mapping_id}; decision={payload.decision}",
        )

        db.commit()
        return dict(db.execute(
            "SELECT * FROM standards_mappings WHERE id=?",
            (mapping_id,),
        ).fetchone())


# Router registration happens after all endpoint definitions.
def register_routes(app):
    app.include_router(router)
