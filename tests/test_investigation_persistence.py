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
        investigation.install(FastAPI(), path)

    def test_six_checkpoints_are_ordered_and_persisted(self):
        def workflow(case_id, run_id, checkpoint):
            for agent in AGENTS:
                checkpoint({"agent": agent, "status": "completed", "result": {}})
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

    def test_checkpoint_does_not_require_human_approval_and_keeps_limitations(self):
        def workflow(case_id, run_id, checkpoint):
            checkpoint({"agent": AGENTS[-1], "status": "completed", "result": {
                "human_review_required": True,
                "automated_approval_permitted": False,
                "review_gates": [{"code": "semantic_assessment_unavailable"}],
                "citations": ["doc#p1"],
            }})
            return {"id": run_id, "case_id": case_id}
        with patch.object(investigation, "_execute_workflow", side_effect=workflow):
            result = investigation.run_workflow("case-a")
        with investigation.connect() as db:
            event = db.execute("SELECT result_json FROM investigation_events WHERE run_id=?",
                               (result["id"],)).fetchone()
        report = json.loads(event["result_json"])["result"]
        self.assertFalse(report["human_review_required"])
        self.assertFalse(report["automated_approval_permitted"])
        self.assertEqual(report["evidence_limitations"], [{"code": "semantic_assessment_unavailable"}])
        self.assertEqual(report["citations"], ["doc#p1"])

    def test_saved_autonomous_report_and_events_show_completed_advisory_analysis(self):
        stage = {"agent": "Policy Advisor", "status": "review_required", "result": {
            "legal_applicability": "not_established", "citations": ["doc#p1"]}}
        report = {"id": "saved-run", "analysis_mode": "autonomous_advisory",
                  "human_review_required": False, "stages": [stage]}
        with investigation.connect() as db:
            db.execute("INSERT INTO investigation_execution (id,case_id,status,created_at,updated_at) VALUES (?,?,?,?,?)",
                       ("saved-run", "case-a", "completed", "2026-11-10", "2026-11-10"))
            db.execute("INSERT INTO investigation_runs VALUES (?,?,?,?)",
                       ("saved-run", "case-a", json.dumps(report), "2026-11-10"))
            db.execute("INSERT INTO investigation_events VALUES (?,?,?,?,?,?)",
                       ("saved-run", 1, "Policy Advisor", "review_required", json.dumps(stage), "2026-11-10"))
        returned = investigation.investigations("case-a")[0]
        events = investigation.execution_events("case-a", "saved-run")
        self.assertEqual(returned["stages"][0]["status"], "completed")
        self.assertEqual(events[0]["status"], "completed")
        self.assertEqual(events[0]["stage"]["status"], "completed")
        self.assertEqual(returned["stages"][0]["result"]["legal_applicability"], "not_established")
        with investigation.connect() as db:
            raw = db.execute("SELECT status FROM investigation_events WHERE run_id='saved-run'").fetchone()
        self.assertEqual(raw["status"], "review_required")

    def test_failure_keeps_checkpoint_history_and_audit(self):
        def workflow(case_id, run_id, checkpoint):
            checkpoint({"agent": AGENTS[0], "status": "completed", "result": {}})
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
