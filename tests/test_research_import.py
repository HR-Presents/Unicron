"""HTTP and database regression tests for research imports."""

import hashlib
import os
import sqlite3
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.evidence import install as install_evidence
from app.research_import import install as install_research_import
from app.research_retrieval import RetrievedDocument, RetrievalError
from app.source_registry import install as install_source_registry


CASE_ID = "CIV-RESEARCH-IMPORT-TEST"
URL = "https://example.org/healthcare-policy.txt"
KEY = "research-test-secret"

PAYLOAD = {
    "url": URL,
    "authority": "Example Health Authority",
    "jurisdiction": "UAE",
    "document_title": "Healthcare Resource Allocation Policy",
    "source_type": "policy",
}


@pytest.fixture
def environment(tmp_path, monkeypatch):
    db_path = tmp_path / "research-import.sqlite3"

    with sqlite3.connect(db_path) as con:
        con.executescript("""
            CREATE TABLE cases (
                id TEXT PRIMARY KEY
            );

            CREATE TABLE audit (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            INSERT INTO cases(id)
            VALUES ('CIV-RESEARCH-IMPORT-TEST');
        """)

    app = FastAPI()

    install_evidence(app, db_path)
    install_source_registry(app, db_path)
    install_research_import(app, db_path)

    monkeypatch.setenv("CIVITAS_API_KEY", KEY)

    return TestClient(app), db_path


def request(client, headers=None):
    return client.post(
        f"/api/cases/{CASE_ID}/research/import",
        json=PAYLOAD,
        headers=headers or {},
    )


def authenticated():
    return {"Authorization": f"Bearer {KEY}"}


def retrieved(payload=b"Article 1\nHealthcare policy requirements."):
    return RetrievedDocument(
        url=URL,
        content_type="text/plain",
        payload=payload,
    )


def test_import_route_registered(environment):
    client, _ = environment
    assert (
        "/api/cases/{case_id}/research/import"
        in client.app.openapi()["paths"]
    )


def test_missing_api_key_configuration_fails_closed(environment, monkeypatch):
    client, _ = environment
    monkeypatch.delenv("CIVITAS_API_KEY")

    with patch("app.research_import.retrieve_isolated") as worker:
        response = request(client, authenticated())

    assert response.status_code == 503
    worker.assert_not_called()


def test_missing_bearer_token_rejected(environment):
    client, _ = environment

    with patch("app.research_import.retrieve_isolated") as worker:
        response = request(client)

    assert response.status_code == 401
    worker.assert_not_called()


def test_wrong_bearer_token_rejected(environment):
    client, _ = environment

    with patch("app.research_import.retrieve_isolated") as worker:
        response = request(
            client,
            {"Authorization": "Bearer incorrect"},
        )

    assert response.status_code == 401
    worker.assert_not_called()


def test_missing_case_does_not_download(environment):
    client, _ = environment

    with patch("app.research_import.retrieve_isolated") as worker:
        response = client.post(
            "/api/cases/UNKNOWN/research/import",
            json=PAYLOAD,
            headers=authenticated(),
        )

    assert response.status_code == 404
    worker.assert_not_called()


def test_successful_import_is_unverified(environment):
    client, db_path = environment

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(),
    ):
        response = request(client, authenticated())

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["verification_status"] == "unverified"
    assert data["human_review_required"] is True
    assert data["passage_count"] >= 1

    with sqlite3.connect(db_path) as con:
        document = con.execute(
            "SELECT sha256 FROM evidence_documents WHERE id=?",
            (data["id"],),
        ).fetchone()

        provenance = con.execute(
            """
            SELECT verification_status, verified_by, verified_at
            FROM source_provenance
            WHERE document_id=?
            """,
            (data["id"],),
        ).fetchone()

        audit_count = con.execute(
            """
            SELECT COUNT(*) FROM audit
            WHERE action='research.document_imported'
            """
        ).fetchone()[0]

    assert document is not None
    assert document[0] == hashlib.sha256(retrieved().payload).hexdigest()
    assert provenance == ("unverified", None, None)
    assert audit_count == 1


def test_duplicate_content_rejected(environment):
    client, db_path = environment

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(),
    ):
        first = request(client, authenticated())
        second = request(client, authenticated())

    assert first.status_code == 201
    assert second.status_code == 409

    with sqlite3.connect(db_path) as con:
        count = con.execute(
            "SELECT COUNT(*) FROM evidence_documents"
        ).fetchone()[0]

    assert count == 1


def test_retrieval_failure_does_not_write(environment):
    client, db_path = environment

    with patch(
        "app.research_import.retrieve_isolated",
        side_effect=RetrievalError("network failure"),
    ):
        response = request(client, authenticated())

    assert response.status_code == 422

    with sqlite3.connect(db_path) as con:
        count = con.execute(
            "SELECT COUNT(*) FROM evidence_documents"
        ).fetchone()[0]

    assert count == 0


def test_invalid_utf8_does_not_write(environment):
    client, db_path = environment

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(b"\xff\xfe"),
    ):
        response = request(client, authenticated())

    assert response.status_code == 422

    with sqlite3.connect(db_path) as con:
        count = con.execute(
            "SELECT COUNT(*) FROM evidence_documents"
        ).fetchone()[0]

    assert count == 0


def test_unsupported_content_type_rejected(environment):
    client, _ = environment

    document = RetrievedDocument(
        url=URL,
        content_type="text/html",
        payload=b"<html>Unsafe</html>",
    )

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=document,
    ):
        response = request(client, authenticated())

    assert response.status_code == 415


def test_oversized_payload_rejected(environment):
    client, _ = environment

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(b"x" * (2 * 1024 * 1024 + 1)),
    ):
        response = request(client, authenticated())

    assert response.status_code == 413


def test_provenance_failure_rolls_back_document(environment):
    client, db_path = environment

    with sqlite3.connect(db_path) as con:
        con.execute("""
            CREATE TRIGGER block_provenance_insert
            BEFORE INSERT ON source_provenance
            BEGIN
                SELECT RAISE(ABORT, 'test rollback');
            END;
        """)

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(),
    ):
        with pytest.raises(sqlite3.DatabaseError):
            request(client, authenticated())

    with sqlite3.connect(db_path) as con:
        documents = con.execute(
            "SELECT COUNT(*) FROM evidence_documents"
        ).fetchone()[0]
        passages = con.execute(
            "SELECT COUNT(*) FROM evidence_passages"
        ).fetchone()[0]

    assert documents == 0
    assert passages == 0


def test_concurrency_limit_rejects_excess_requests(environment):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock

    client, db_path = environment
    entered = Event()
    release = Event()
    lock = Lock()
    active = 0

    def blocked_retrieval(url):
        nonlocal active
        with lock:
            active += 1
            if active == 2:
                entered.set()

        if not release.wait(timeout=5):
            raise RetrievalError("test synchronization timeout")

        return retrieved()

    with patch(
        "app.research_import.retrieve_isolated",
        side_effect=blocked_retrieval,
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(request, client, authenticated())
                for _ in range(2)
            ]

            try:
                assert entered.wait(timeout=5), (
                    "Two retrieval workers did not enter concurrently"
                )

                third = request(client, authenticated())
                assert third.status_code == 429
            finally:
                release.set()

            results = [future.result() for future in futures]

    assert sorted(r.status_code for r in results) == [201, 409]


def test_failed_retrieval_releases_capacity(environment):
    client, _ = environment

    with patch(
        "app.research_import.retrieve_isolated",
        side_effect=RetrievalError("temporary failure"),
    ):
        for _ in range(3):
            response = request(client, authenticated())
            assert response.status_code == 422

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(),
    ):
        response = request(client, authenticated())

    assert response.status_code == 201


def test_imported_document_requires_reviewer_key(environment, monkeypatch):
    client, db_path = environment

    monkeypatch.setenv(
        "CIVITAS_REVIEWER_API_KEY",
        "separate-reviewer-secret",
    )

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(),
    ):
        imported = request(client, authenticated())

    assert imported.status_code == 201
    document_id = imported.json()["id"]

    response = client.post(
        f"/api/cases/{CASE_ID}/evidence/{document_id}/verify",
        json={
            "decision": "verified",
            "reviewer": "Test Reviewer",
            "rationale": "Reviewed URL, authority and document content.",
            "checked_url": True,
            "checked_authority": True,
            "checked_document": True,
        },
        headers=authenticated(),
    )

    assert response.status_code == 401

    with sqlite3.connect(db_path) as con:
        status = con.execute(
            """
            SELECT verification_status
            FROM source_provenance
            WHERE document_id=?
            """,
            (document_id,),
        ).fetchone()[0]

    assert status == "unverified"


def test_claimed_metadata_cannot_self_verify(environment):
    client, db_path = environment

    payload = {
        **PAYLOAD,
        "verification_status": "verified",
        "verified_by": "Automated Importer",
    }

    with patch(
        "app.research_import.retrieve_isolated",
        return_value=retrieved(),
    ):
        response = client.post(
            f"/api/cases/{CASE_ID}/research/import",
            json=payload,
            headers=authenticated(),
        )

    assert response.status_code == 201
    assert response.json()["verification_status"] == "unverified"

    with sqlite3.connect(db_path) as con:
        status = con.execute(
            """
            SELECT verification_status, verified_by
            FROM source_provenance
            WHERE document_id=?
            """,
            (response.json()["id"],),
        ).fetchone()

    assert status == ("unverified", None)
