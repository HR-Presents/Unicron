"""Regression checks for evidence cache selection and freshness."""
import json
import sqlite3
import unittest
from pathlib import Path

from backend.app import investigation


class EvidenceCacheTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE evidence_runs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO evidence_runs VALUES
                ('old', 'case1', '{"marker":"old"}', '2026-11-09T10:00:00'),
                ('new', 'case1', '{"marker":"new"}', '2026-11-09T10:00:00');
        """)

    def test_latest_result_and_fingerprint_select_same_row(self):
        latest = investigation.latest_json(
            self.db, "evidence_runs", "case1", "result_json"
        )
        row = self.db.execute(
            """SELECT result_json FROM evidence_runs
               WHERE case_id=?
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            ("case1",)
        ).fetchone()

        self.assertEqual(
            latest,
            json.loads(row["result_json"]),
            "Evidence result and fingerprint must come from the same run",
        )

    def test_workflow_has_no_timestamp_only_freshness_gate(self):
        source = Path(investigation.__file__).read_text()
        self.assertIn("stored_fingerprint != current_fingerprint", source)
        self.assertNotIn("latest_document > latest_analysis", source)

    def test_workflow_rejects_mid_analysis_input_change(self):
        source = Path(investigation.__file__).read_text()
        self.assertIn("BEGIN IMMEDIATE", source)
        self.assertIn(
            "evidence_fingerprint(db, case_id) != current_fingerprint",
            source,
        )


if __name__ == "__main__":
    unittest.main()
