import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import standards_registry


@pytest.fixture
def standards_client():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "standards.sqlite3")

        with sqlite3.connect(path) as db:
            db.executescript("""
            CREATE TABLE cases (id TEXT PRIMARY KEY);
            CREATE TABLE evidence_documents (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL
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
            INSERT INTO evidence_documents VALUES ('D1','C1'), ('D2','C2');
            INSERT INTO evidence_passages VALUES ('P1','D1'), ('P2','D2');
            INSERT INTO source_provenance VALUES
                ('D1','verified'), ('D2','unverified');
            """)

        app = FastAPI()
        standards_registry.install(app, path)

        with patch.dict(
            os.environ,
            {"CIVITAS_REVIEWER_API_KEY": "test-secret"},
        ):
            yield TestClient(app), path


HEADERS = {"X-Reviewer-Key": "test-secret"}


def setup_requirement(client):
    framework = client.post(
        "/api/standards/frameworks",
        headers=HEADERS,
        json={
            "identifier": "TEST-RMF",
            "title": "Test Governance Framework",
            "publisher": "Test Standards Authority",
            "edition": "2026",
            "official_url": "https://example.org/framework",
            "normative_status": "guidance",
        },
    )
    assert framework.status_code == 201, framework.text

    requirement = client.post(
        "/api/standards/requirements",
        headers=HEADERS,
        json={
            "framework_id": "TEST-RMF",
            "requirement_code": "GOV-1",
            "description": "Document governance responsibilities.",
        },
    )
    assert requirement.status_code == 201, requirement.text
    return requirement.json()["id"]


def mapping_payload(requirement_id, passage_id="P1"):
    return {
        "requirement_id": requirement_id,
        "passage_id": passage_id,
        "assessment": "needs_review",
        "rationale": "This passage may support governance responsibilities.",
    }


def test_reviewer_authentication(standards_client):
    client, _ = standards_client

    response = client.post(
        "/api/standards/frameworks",
        json={
            "identifier": "TEST-RMF",
            "title": "Test Governance Framework",
            "publisher": "Test Authority",
            "edition": "2026",
            "official_url": "https://example.org/framework",
            "normative_status": "guidance",
        },
    )
    assert response.status_code == 401


def test_framework_duplicate_rejected(standards_client):
    client, _ = standards_client
    setup_requirement(client)

    response = client.post(
        "/api/standards/frameworks",
        headers=HEADERS,
        json={
            "identifier": "TEST-RMF",
            "title": "Duplicate Framework",
            "publisher": "Test Authority",
            "edition": "2026",
            "official_url": "https://example.org/framework",
            "normative_status": "guidance",
        },
    )
    assert response.status_code == 409


def test_cross_case_mapping_rejected(standards_client):
    client, _ = standards_client
    requirement_id = setup_requirement(client)

    response = client.post(
        "/api/cases/C2/standards/mappings",
        headers=HEADERS,
        json=mapping_payload(requirement_id),
    )
    assert response.status_code == 422


def test_unverified_source_rejected(standards_client):
    client, _ = standards_client
    requirement_id = setup_requirement(client)

    response = client.post(
        "/api/cases/C2/standards/mappings",
        headers=HEADERS,
        json=mapping_payload(requirement_id, "P2"),
    )
    assert response.status_code == 422


def test_duplicate_mapping_and_audit(standards_client):
    client, path = standards_client
    requirement_id = setup_requirement(client)
    endpoint = "/api/cases/C1/standards/mappings"
    payload = mapping_payload(requirement_id)

    first = client.post(endpoint, headers=HEADERS, json=payload)
    second = client.post(endpoint, headers=HEADERS, json=payload)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert len(client.get(endpoint).json()) == 1

    with sqlite3.connect(path) as db:
        count = db.execute(
            """SELECT COUNT(*) FROM audit
               WHERE action='standards.mapping_created'"""
        ).fetchone()[0]
    assert count == 1


def test_review_is_immutable(standards_client):
    client, path = standards_client
    requirement_id = setup_requirement(client)

    created = client.post(
        "/api/cases/C1/standards/mappings",
        headers=HEADERS,
        json=mapping_payload(requirement_id),
    )
    assert created.status_code == 201, created.text

    endpoint = (
        "/api/cases/C1/standards/mappings/"
        + created.json()["id"]
        + "/review"
    )
    decision = {
        "decision": "verified",
        "reviewer": "Test Reviewer",
        "rationale": "The cited evidence and relationship were reviewed.",
    }

    first = client.post(endpoint, headers=HEADERS, json=decision)
    second = client.post(endpoint, headers=HEADERS, json=decision)

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert first.json()["review_status"] == "verified"

    with sqlite3.connect(path) as db:
        count = db.execute(
            """SELECT COUNT(*) FROM audit
               WHERE action='standards.mapping_reviewed'"""
        ).fetchone()[0]
    assert count == 1
