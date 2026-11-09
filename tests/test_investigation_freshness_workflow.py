"""Workflow-level evidence freshness tests with isolated SQLite state."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app import investigation


class StopAfterEvidence(Exception):
    """Stop after the evidence cache decision, before downstream agents."""


class InvestigationFreshnessWorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = str(Path(temporary.name) / "workflow.sqlite3")

        previous = investigation.DB_PATH
        investigation.DB_PATH = self.path
        self.addCleanup(setattr, investigation, "DB_PATH", previous)

        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE cases (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    summary TEXT
                );
                INSERT INTO cases VALUES ('case1', 'Test case', 'Test summary');

                CREATE TABLE evidence_documents (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    filename TEXT,
                    source_note TEXT,
                    sha256 TEXT,
                    passage_count INTEGER,
                    created_at TEXT
                );
                INSERT INTO evidence_documents VALUES
                    ('doc1', 'case1', 'policy.pdf', 'policy', 'abc', 1,
                     '2026-11-09T10:00:00');

                CREATE TABLE evidence_passages (
                    id TEXT PRIMARY KEY,
                    document_id TEXT,
                    position INTEGER,
                    content TEXT,
                    created_at TEXT
                );
                INSERT INTO evidence_passages VALUES
                    ('p1', 'doc1', 0, 'Evidence content',
                     '2026-11-09T10:00:00');

                CREATE TABLE source_provenance (
                    document_id TEXT PRIMARY KEY,
                    authority TEXT,
                    jurisdiction TEXT,
                    document_title TEXT,
                    official_url TEXT,
                    publication_date TEXT,
                    effective_date TEXT,
                    source_type TEXT,
                    verification_status TEXT,
                    verified_by TEXT,
                    verified_at TEXT
                );
                INSERT INTO source_provenance (
                    document_id, verification_status
                ) VALUES ('doc1', 'unverified');

                CREATE TABLE triage_runs (
                    case_id TEXT,
                    result_json TEXT,
                    created_at TEXT
                );
                INSERT INTO triage_runs VALUES
                    ('case1', '{}', '2026-11-09T10:00:00');

                CREATE TABLE evidence_runs (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    model TEXT,
                    result_json TEXT,
                    excerpts_json TEXT,
                    created_at TEXT
                );

                CREATE TABLE audit (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    action TEXT,
                    detail TEXT,
                    created_at TEXT
                );
            """)

    def seed_cached_result(self, fingerprint):
        result = {"findings": []}
        if fingerprint is not None:
            result["_evidence_fingerprint"] = fingerprint

        with investigation.connect() as db:
            db.execute(
                """INSERT INTO evidence_runs VALUES
                   (?, ?, ?, ?, ?, ?)""",
                (
                    "cached", "case1", "test-model",
                    json.dumps(result), "[]",
                    "2026-11-09T10:01:00",
                ),
            )
            db.commit()

    def current_fingerprint(self):
        with investigation.connect() as db:
            return investigation.evidence_fingerprint(db, "case1")

    def run_until_downstream(self, analyze):
        def stop_at_policy(*args, **kwargs):
            raise StopAfterEvidence()

        with (
            patch.object(
                investigation,
                "retrieve_knowledge",
                return_value=[],
            ),
            patch.object(
                investigation,
                "policy_stage",
                side_effect=stop_at_policy,
            ),
            patch("backend.app.evidence.analyze_evidence", side_effect=analyze),
        ):
            with self.assertRaises(StopAfterEvidence):
                investigation._execute_workflow(
                    "case1", "run1", lambda stage, fingerprint: None
                )

    def test_unchanged_evidence_reuses_cached_result(self):
        self.seed_cached_result(self.current_fingerprint())

        def unexpected_analysis(case_id):
            self.fail("Unchanged evidence must reuse the cached result")

        self.run_until_downstream(unexpected_analysis)

    def test_legacy_result_requires_reanalysis(self):
        self.seed_cached_result(None)

        def analyze(case_id):
            raise RuntimeError("REANALYSIS_REQUESTED")

        with (
            patch.object(investigation, "retrieve_knowledge", return_value=[]),
            patch("backend.app.evidence.analyze_evidence", side_effect=analyze),
        ):
            with self.assertRaisesRegex(RuntimeError, "REANALYSIS_REQUESTED"):
                investigation._execute_workflow(
                    "case1", "run1", lambda stage, fingerprint: None
                )

    def test_verification_change_requires_reanalysis(self):
        self.seed_cached_result(self.current_fingerprint())

        with investigation.connect() as db:
            db.execute(
                """UPDATE source_provenance
                   SET verification_status='verified',
                       verified_by='reviewer'
                   WHERE document_id='doc1'"""
            )
            db.commit()

        def analyze(case_id):
            raise RuntimeError("REANALYSIS_REQUESTED")

        with (
            patch.object(investigation, "retrieve_knowledge", return_value=[]),
            patch("backend.app.evidence.analyze_evidence", side_effect=analyze),
        ):
            with self.assertRaisesRegex(RuntimeError, "REANALYSIS_REQUESTED"):
                investigation._execute_workflow(
                    "case1", "run1", lambda stage, fingerprint: None
                )


    def test_passage_edit_requires_reanalysis(self):
        self.seed_cached_result(self.current_fingerprint())

        with investigation.connect() as db:
            db.execute(
                "UPDATE evidence_passages SET content=? WHERE id='p1'",
                ("Modified evidence content",),
            )
            db.commit()

        def analyze(case_id):
            raise RuntimeError("REANALYSIS_REQUESTED")

        with (
            patch.object(investigation, "retrieve_knowledge", return_value=[]),
            patch("backend.app.evidence.analyze_evidence", side_effect=analyze),
        ):
            with self.assertRaisesRegex(RuntimeError, "REANALYSIS_REQUESTED"):
                investigation._execute_workflow(
                    "case1", "run1", lambda stage, fingerprint: None
                )

    def test_mid_analysis_change_rejects_fingerprint_certification(self):
        from fastapi import HTTPException

        def analyze(case_id):
            with investigation.connect() as db:
                db.execute(
                    "UPDATE evidence_passages SET content=? WHERE id='p1'",
                    ("Changed during inference",),
                )
                db.execute(
                    """INSERT INTO evidence_runs VALUES
                       (?, ?, ?, ?, ?, ?)""",
                    (
                        "newrun", "case1", "test-model",
                        json.dumps({"findings": []}), "[]",
                        "2026-11-09T10:02:00",
                    ),
                )
                db.commit()
            return {"id": "newrun", "result": {"findings": []}}

        with (
            patch.object(investigation, "retrieve_knowledge", return_value=[]),
            patch("backend.app.evidence.analyze_evidence", side_effect=analyze),
        ):
            with self.assertRaises(HTTPException) as caught:
                investigation._execute_workflow(
                    "case1", "run1", lambda stage, fingerprint: None
                )

        self.assertEqual(caught.exception.status_code, 409)
        with investigation.connect() as db:
            row = db.execute(
                "SELECT result_json FROM evidence_runs WHERE id='newrun'"
            ).fetchone()
        self.assertNotIn(
            "_evidence_fingerprint", json.loads(row["result_json"])
        )

    def test_deleted_evidence_does_not_trigger_old_analysis(self):
        self.seed_cached_result(self.current_fingerprint())

        with investigation.connect() as db:
            db.execute("DELETE FROM evidence_passages")
            db.execute("DELETE FROM source_provenance")
            db.execute("DELETE FROM evidence_documents")
            db.commit()

        def unexpected_analysis(case_id):
            self.fail("No evidence remains; must not call Evidence Analyst")

        self.run_until_downstream(unexpected_analysis)


    def test_analyst_snapshot_mismatch_is_rejected(self):
        from fastapi import HTTPException

        def analyze(case_id):
            with investigation.connect() as db:
                db.execute(
                    """INSERT INTO evidence_runs VALUES
                       (?, ?, ?, ?, ?, ?)""",
                    (
                        "mismatch", "case1", "test-model",
                        json.dumps({"findings": []}), "[]",
                        "2026-11-09T10:02:00",
                    ),
                )
                db.commit()

            return {
                "id": "mismatch",
                "result": {"findings": []},
                "input_evidence_fingerprint": "incorrect-snapshot",
            }

        with (
            patch.object(investigation, "retrieve_knowledge", return_value=[]),
            patch("backend.app.evidence.analyze_evidence", side_effect=analyze),
        ):
            with self.assertRaises(HTTPException) as caught:
                investigation._execute_workflow(
                    "case1", "run1", lambda stage, fingerprint: None
                )

        self.assertEqual(caught.exception.status_code, 409)

        with investigation.connect() as db:
            row = db.execute(
                "SELECT result_json FROM evidence_runs WHERE id='mismatch'"
            ).fetchone()

        self.assertNotIn(
            "_evidence_fingerprint", json.loads(row["result_json"])
        )

    def test_matching_analyst_snapshot_is_certified(self):
        fingerprint = self.current_fingerprint()

        def analyze(case_id):
            with investigation.connect() as db:
                db.execute(
                    """INSERT INTO evidence_runs VALUES
                       (?, ?, ?, ?, ?, ?)""",
                    (
                        "matched", "case1", "test-model",
                        json.dumps({"findings": []}), "[]",
                        "2026-11-09T10:02:00",
                    ),
                )
                db.commit()

            return {
                "id": "matched",
                "result": {"findings": []},
                "input_evidence_fingerprint": fingerprint,
            }

        self.run_until_downstream(analyze)

        with investigation.connect() as db:
            row = db.execute(
                "SELECT result_json FROM evidence_runs WHERE id='matched'"
            ).fetchone()

        self.assertEqual(
            json.loads(row["result_json"])["_evidence_fingerprint"],
            fingerprint,
        )


if __name__ == "__main__":
    unittest.main()
