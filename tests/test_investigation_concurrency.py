"""Database integration tests for concurrent investigation exclusion."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from backend.app import investigation


class InvestigationConcurrencyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = str(Path(temp.name) / "investigation.sqlite3")
        previous = investigation.DB_PATH
        self.addCleanup(setattr, investigation, "DB_PATH", previous)
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE cases (id TEXT PRIMARY KEY)")
            db.execute("INSERT INTO cases VALUES ('case-a')")
            db.execute("CREATE TABLE audit (id TEXT PRIMARY KEY, case_id TEXT, action TEXT, detail TEXT, created_at TEXT)")
            db.execute("""
                CREATE TABLE evidence_documents (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    filename TEXT,
                    source_note TEXT,
                    sha256 TEXT,
                    passage_count INTEGER
                )
            """)
            db.execute("""
                CREATE TABLE evidence_passages (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    content TEXT NOT NULL
                )
            """)
        investigation.install(FastAPI(), path)

    def test_second_execution_rejected_while_first_is_running(self):
        def concurrent_attempt(case_id, run_id, checkpoint):
            with self.assertRaises(HTTPException) as raised:
                investigation.run_workflow(case_id)
            self.assertEqual(raised.exception.status_code, 409)
            checkpoint({"agent": "Intake & Triage", "status": "completed", "result": {}}, _checkpoint_fingerprint(case_id))
            return {"id": run_id, "human_review_required": True}

        with patch.object(investigation, "_execute_workflow", side_effect=concurrent_attempt):
            result = investigation.run_workflow("case-a")

        with investigation.connect() as db:
            rows = db.execute("SELECT status, error_type FROM investigation_execution ORDER BY created_at").fetchall()
            events = db.execute("SELECT agent FROM investigation_events").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "completed")
        self.assertEqual([row["agent"] for row in events], ["Intake & Triage"])
        self.assertTrue(result["human_review_required"])

    def test_failed_execution_releases_running_lock(self):
        with patch.object(investigation, "_execute_workflow", side_effect=ValueError("synthetic")):
            with self.assertRaises(ValueError):
                investigation.run_workflow("case-a")

        with patch.object(investigation, "_execute_workflow", side_effect=lambda case_id, run_id, checkpoint: {"id": run_id}):
            result = investigation.run_workflow("case-a")

        with investigation.connect() as db:
            statuses = [row["status"] for row in db.execute("SELECT status FROM investigation_execution ORDER BY created_at, id")]
        self.assertCountEqual(statuses, ["failed", "completed"])
        self.assertIsNotNone(result["id"])


if __name__ == "__main__":
    unittest.main()


def _checkpoint_fingerprint(case_id):
    with investigation.connect() as db:
        return investigation.evidence_fingerprint(db, case_id)
