"""Real FastAPI application integration checks for research import."""

import os
import subprocess
import sys
import textwrap


def test_main_application_research_import(tmp_path):
    db_path = tmp_path / "main-app-test.sqlite3"

    script = textwrap.dedent("""
        import sqlite3
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.main import app
        from app.research_retrieval import RetrievedDocument

        case_id = "CIV-IMPORT-MAIN-TEST"

        with sqlite3.connect(os.environ["CIVITAS_DB_PATH"]) as con:
            con.execute(
                "INSERT INTO cases VALUES (?,?,?,?,?,?,?,?)",
                (
                    case_id,
                    "Research integration test",
                    "Temporary integration test case",
                    "Healthcare",
                    "Medium",
                    "New",
                    "2026-11-08T00:00:00+00:00",
                    "2026-11-08T00:00:00+00:00",
                ),
            )

        client = TestClient(app)

        payload = {
            "url": "https://example.org/policy.txt",
            "authority": "Example Health Authority",
            "jurisdiction": "UAE",
            "document_title": "Healthcare Resource Allocation",
            "source_type": "policy",
        }

        document = RetrievedDocument(
            url=payload["url"],
            content_type="text/plain",
            payload=b"Article 1\\nHealthcare resource allocation policy.",
        )

        with patch(
            "app.research_import.retrieve_isolated",
            return_value=document,
        ) as worker:
            unauthenticated = client.post(
                f"/api/cases/{case_id}/research/import",
                json=payload,
            )
            assert unauthenticated.status_code == 401
            worker.assert_not_called()

            authenticated = client.post(
                f"/api/cases/{case_id}/research/import",
                json=payload,
                headers={
                    "Authorization": "Bearer integration-test-secret"
                },
            )

        assert authenticated.status_code == 201, authenticated.text
        result = authenticated.json()
        assert result["verification_status"] == "unverified"

        with sqlite3.connect(os.environ["CIVITAS_DB_PATH"]) as con:
            stored = con.execute(
                '''
                SELECT p.verification_status, d.case_id
                FROM source_provenance p
                JOIN evidence_documents d ON d.id=p.document_id
                WHERE d.id=?
                ''',
                (result["id"],),
            ).fetchone()

        assert stored == ("unverified", case_id)
        print("MAIN APPLICATION IMPORT INTEGRATION: PASSED")
    """)

    environment = os.environ.copy()
    environment["CIVITAS_DB_PATH"] = str(db_path)
    environment["CIVITAS_API_KEY"] = "integration-test-secret"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os\n" + script,
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout + "\n" + result.stderr
    )
    assert "MAIN APPLICATION IMPORT INTEGRATION: PASSED" in result.stdout
