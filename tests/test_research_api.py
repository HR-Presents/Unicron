"""HTTP integration tests for case research discovery."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, db
from app.research_discovery import DiscoveredSource
from app.research_pipeline import ResearchDiscoveryResult


client = TestClient(app)

CASE_ID = "CIV-RESEARCH-HTTP-TEST"


def test_research_endpoint_registered():
    path = "/api/cases/{case_id}/research/discover"

    schema = app.openapi()
    operations = schema["paths"].get(path, {})

    assert "post" in operations


def test_missing_case_returns_404():
    with patch(
        "app.research_api.discover_case_research"
    ) as discovery:
        response = client.post(
            "/api/cases/CIV-NONEXISTENT-RESEARCH-TEST/research/discover"
        )

    assert response.status_code == 404
    discovery.assert_not_called()


def test_existing_case_returns_unverified_candidates():
    with db() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO cases
            (id, title, summary, domain, priority,
             status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                CASE_ID,
                "Healthcare Policy Research",
                "Evaluate healthcare resource allocation",
                "Healthcare",
                "Medium",
                "New",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )

    result = ResearchDiscoveryResult(
        queries=("UAE healthcare policy",),
        candidates=(
            DiscoveredSource(
                title="Healthcare Policy",
                url="https://example.org/policy",
                description="Official policy candidate",
                query="UAE healthcare policy",
            ),
        ),
        errors=(),
    )

    try:
        with patch(
            "app.research_api.discover_case_research",
            return_value=result,
        ) as discovery:
            response = client.post(
                f"/api/cases/{CASE_ID}/research/discover"
            )

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["case_id"] == CASE_ID
        assert data["verification_status"] == "unverified"
        assert data["human_review_required"] is True
        assert data["evidence_imported"] is False
        assert len(data["candidates"]) == 1
        assert (
            data["candidates"][0]["verification_status"]
            == "unverified"
        )

        discovery.assert_called_once()

        with db() as con:
            evidence_count = con.execute(
                """
                SELECT COUNT(*) FROM evidence_documents
                WHERE case_id=?
                """,
                (CASE_ID,),
            ).fetchone()[0]

        assert evidence_count == 0

    finally:
        with db() as con:
            con.execute(
                "DELETE FROM cases WHERE id=?",
                (CASE_ID,),
            )
