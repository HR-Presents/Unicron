"""Standards lifecycle integration without touching production case data."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class StandardsLifecycleTest(unittest.TestCase):
    def test_framework_requirement_mapping_review_and_traceability(self):
        from backend.app import main
        from backend.app import standards_registry
        from backend.app import investigation

        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "standards-test.sqlite3"

            # Use a copy of the existing schema, not the user's live database.
            source = sqlite3.connect(main.DB_PATH)
            target = sqlite3.connect(db_path)
            try:
                source.backup(target)
            finally:
                source.close()
                target.close()

            with patch.object(standards_registry, "DB_PATH", str(db_path)), \
                 patch.object(investigation, "DB_PATH", str(db_path)), \
                 patch.dict(os.environ, {
                     "CIVITAS_REVIEWER_API_KEY": "test-reviewer-secret"
                 }):

                client = TestClient(main.app)
                headers = {"x-reviewer-key": "test-reviewer-secret"}

                framework = {
                    "identifier": "TEST-TRACEABILITY-2026",
                    "title": "Isolated Traceability Test Framework",
                    "publisher": "Integration Test",
                    "edition": "2026",
                    "official_url": "https://example.org/standards/test",
                    "normative_status": "unknown",
                }

                response = client.post(
                    "/api/standards/frameworks",
                    json=framework,
                    headers=headers,
                )
                self.assertEqual(response.status_code, 201, response.text)

                requirement = client.post(
                    "/api/standards/requirements",
                    json={
                        "framework_id": framework["identifier"],
                        "requirement_code": "TRACE-01",
                        "description": "Evidence associations must be reviewed.",
                    },
                    headers=headers,
                )
                self.assertEqual(
                    requirement.status_code, 201, requirement.text
                )

                requirement_id = requirement.json()["id"]

                # Synthetic evidence exists ONLY in the temporary database.
                # This verifies the lifecycle without changing real provenance.
                from datetime import datetime, timezone
                from uuid import uuid4

                timestamp = datetime.now(timezone.utc).isoformat()
                case_id = "CIV-TEST-" + uuid4().hex[:12]
                document_id = str(uuid4())
                passage_id = str(uuid4())

                with sqlite3.connect(db_path) as db:
                    db.execute("PRAGMA foreign_keys=ON")

                    db.execute(
                        """INSERT INTO cases
                           (id,title,summary,domain,priority,status,
                            created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            case_id,
                            "Synthetic governance test",
                            "Isolated standards lifecycle fixture",
                            "governance",
                            "medium",
                            "open",
                            timestamp,
                            timestamp,
                        ),
                    )

                    db.execute(
                        """INSERT INTO evidence_documents
                           (id,case_id,filename,source_note,sha256,
                            passage_count,created_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (
                            document_id,
                            case_id,
                            "synthetic-evidence.txt",
                            "Synthetic integration test only",
                            "0" * 64,
                            1,
                            timestamp,
                        ),
                    )

                    db.execute(
                        """INSERT INTO evidence_passages
                           (id,document_id,position,content,created_at)
                           VALUES (?,?,?,?,?)""",
                        (
                            passage_id,
                            document_id,
                            1,
                            "Synthetic passage for verifying standards "
                            "mapping and human review behavior.",
                            timestamp,
                        ),
                    )

                    db.execute(
                        """INSERT INTO source_provenance
                           (document_id,authority,jurisdiction,
                            document_title,official_url,source_type,
                            verification_status,verified_by,
                            verification_rationale,verified_at,created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            document_id,
                            "Synthetic Test Authority",
                            "TEST",
                            "Synthetic evidence fixture",
                            "https://example.org/synthetic-evidence",
                            "guidance",
                            "verified",
                            "Integration Test Reviewer",
                            "Synthetic provenance approved only "
                            "inside the isolated test database.",
                            timestamp,
                            timestamp,
                        ),
                    )

                    db.commit()

                mapping = client.post(
                    f"/api/cases/{case_id}/standards/mappings",
                    json={
                        "requirement_id": requirement_id,
                        "passage_id": passage_id,
                        "assessment": "needs_review",
                        "rationale": (
                            "This passage is associated with the "
                            "test requirement for reviewer assessment."
                        ),
                    },
                    headers=headers,
                )
                self.assertEqual(mapping.status_code, 201, mapping.text)

                mapping_id = mapping.json()["id"]

                reviewed = client.post(
                    f"/api/cases/{case_id}/standards/"
                    f"mappings/{mapping_id}/review",
                    json={
                        "decision": "verified",
                        "reviewer": "Integration Test Reviewer",
                        "rationale": (
                            "The association was checked against "
                            "the verified source passage."
                        ),
                    },
                    headers=headers,
                )
                self.assertEqual(reviewed.status_code, 201, reviewed.text)

                trace = investigation.standards_traceability(case_id)

                self.assertEqual(trace["compliance_status"], "not_determined")
                self.assertGreaterEqual(trace["counts"]["verified"], 1)

                self.assertTrue(any(
                    item["id"] == mapping_id
                    for item in trace["mappings"]
                ))

                duplicate_review = client.post(
                    f"/api/cases/{case_id}/standards/"
                    f"mappings/{mapping_id}/review",
                    json={
                        "decision": "rejected",
                        "reviewer": "Integration Test Reviewer",
                        "rationale": "Attempted second decision must fail.",
                    },
                    headers=headers,
                )
                self.assertEqual(duplicate_review.status_code, 409)


if __name__ == "__main__":
    unittest.main()
