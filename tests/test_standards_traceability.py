import os
import sqlite3
import tempfile
from unittest.mock import patch

from backend.app import investigation, standards_registry


def test_standards_traceability_review_and_case_isolation():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "standards.sqlite3")

        with sqlite3.connect(path) as db:
            db.executescript("""
                CREATE TABLE cases (id TEXT PRIMARY KEY);
                CREATE TABLE evidence_documents (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    filename TEXT NOT NULL
                );
                CREATE TABLE evidence_passages (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL
                );
                CREATE TABLE source_provenance (
                    document_id TEXT PRIMARY KEY,
                    verification_status TEXT NOT NULL
                );
                CREATE TABLE audit (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    action TEXT,
                    detail TEXT,
                    created_at TEXT
                );

                INSERT INTO cases VALUES ('C1'), ('C2');
                INSERT INTO evidence_documents VALUES
                    ('D1','C1','policy.txt'),
                    ('D2','C2','other.txt');
                INSERT INTO evidence_passages VALUES
                    ('P1','D1'), ('P2','D2');
                INSERT INTO source_provenance VALUES
                    ('D1','verified'), ('D2','verified');
            """)

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        standards_registry.install(app, path)
        client = TestClient(app)

        headers = {"X-Reviewer-Key": "test-secret"}

        with patch.dict(
            os.environ,
            {"CIVITAS_REVIEWER_API_KEY": "test-secret"},
        ), patch.object(investigation, "DB_PATH", path):

            framework = client.post(
                "/api/standards/frameworks",
                headers=headers,
                json={
                    "identifier": "TEST-FRAMEWORK",
                    "title": "Test Standards Framework",
                    "publisher": "Test Authority",
                    "edition": "2026",
                    "official_url": "https://example.org/standard",
                    "normative_status": "guidance",
                },
            )
            assert framework.status_code == 201, framework.text

            requirement = client.post(
                "/api/standards/requirements",
                headers=headers,
                json={
                    "framework_id": "TEST-FRAMEWORK",
                    "requirement_code": "REQ-1",
                    "description": "Document governance responsibilities.",
                },
            )
            assert requirement.status_code == 201, requirement.text

            mapping = client.post(
                "/api/cases/C1/standards/mappings",
                headers=headers,
                json={
                    "requirement_id": requirement.json()["id"],
                    "passage_id": "P1",
                    "assessment": "needs_review",
                    "rationale": "This evidence may address governance.",
                },
            )
            assert mapping.status_code == 201, mapping.text

            pending = investigation.standards_traceability("C1")
            assert pending["counts"]["pending"] == 1
            assert pending["counts"]["verified"] == 0
            assert pending["compliance_status"] == "not_determined"

            other_case = investigation.standards_traceability("C2")
            assert other_case["mappings"] == []

            review = client.post(
                f"/api/cases/C1/standards/mappings/"
                f"{mapping.json()['id']}/review",
                headers=headers,
                json={
                    "decision": "verified",
                    "reviewer": "Test Reviewer",
                    "rationale": "Reviewed source and mapping rationale.",
                },
            )
            assert review.status_code == 201, review.text

            verified = investigation.standards_traceability("C1")
            assert verified["counts"]["verified"] == 1

            with sqlite3.connect(path) as db:
                db.execute(
                    "UPDATE source_provenance "
                    "SET verification_status='rejected' "
                    "WHERE document_id='D1'"
                )
                db.commit()

            stale = investigation.standards_traceability("C1")
            assert stale["counts"]["verified"] == 0
            assert stale["counts"]["source_reverification_required"] == 1
            assert stale["compliance_status"] == "not_determined"
