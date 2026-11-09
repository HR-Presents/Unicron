"""Integration tests for durable six-agent execution records and review gates."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from backend.app import investigation

AGENTS = (
    "Intake & Triage", "Evidence Analyst", "Policy Advisor",
    "Global Benchmark Agent", "Scenario Evaluator", "Review & Synthesis",
)


class InvestigationPersistenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = str(Path(tmp.name) / "investigation.sqlite3")
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

    def test_six_checkpoints_are_ordered_and_persisted(self):
        def workflow(case_id, run_id, checkpoint):
            for agent in AGENTS:
                checkpoint({"agent": agent, "status": "completed", "result": {}}, _checkpoint_fingerprint(case_id))
            return {"id": run_id, "case_id": case_id, "human_review_required": True}

        with patch.object(investigation, "_execute_workflow", side_effect=workflow):
            result = investigation.run_workflow("case-a")

        self.assertTrue(result["human_review_required"])
        with investigation.connect() as db:
            execution = db.execute("SELECT * FROM investigation_execution WHERE id=?", (result["id"],)).fetchone()
            events = db.execute("SELECT sequence, agent FROM investigation_events WHERE run_id=? ORDER BY sequence", (result["id"],)).fetchall()
        self.assertEqual(execution["status"], "completed")
        self.assertEqual(execution["last_agent"], AGENTS[-1])
        self.assertEqual([row["agent"] for row in events], list(AGENTS))
        self.assertEqual([row["sequence"] for row in events], list(range(1, 7)))

    def test_failure_keeps_checkpoint_history_and_audit(self):
        def workflow(case_id, run_id, checkpoint):
            checkpoint({"agent": AGENTS[0], "status": "completed", "result": {}}, _checkpoint_fingerprint(case_id))
            raise ValueError("synthetic workflow failure")

        with patch.object(investigation, "_execute_workflow", side_effect=workflow):
            with self.assertRaises(ValueError):
                investigation.run_workflow("case-a")

        with investigation.connect() as db:
            execution = db.execute("SELECT * FROM investigation_execution").fetchone()
            events = db.execute("SELECT agent FROM investigation_events WHERE run_id=?", (execution["id"],)).fetchall()
            audit = db.execute("SELECT action FROM audit").fetchall()
        self.assertEqual(execution["status"], "failed")
        self.assertEqual(execution["error_type"], "ValueError")
        self.assertEqual([row["agent"] for row in events], [AGENTS[0]])
        self.assertIn("agent.investigation_failed", [row["action"] for row in audit])


if __name__ == "__main__":
    unittest.main()


def _checkpoint_fingerprint(case_id):
    with investigation.connect() as db:
        return investigation.evidence_fingerprint(db, case_id)
