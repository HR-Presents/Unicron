"""Regression tests for cached Evidence Analyst citation provenance."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app import investigation


class CachedEvidenceProvenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = str(Path(tmp.name) / "cache.sqlite3")

        previous = investigation.DB_PATH
        self.addCleanup(setattr, investigation, "DB_PATH", previous)
        investigation.DB_PATH = db_path

        with sqlite3.connect(db_path) as db:
            db.executescript("""
                CREATE TABLE evidence_documents (
                    id TEXT PRIMARY KEY,
                    case_id TEXT,
                    filename TEXT
                );
                CREATE TABLE evidence_passages (
                    id TEXT PRIMARY KEY,
                    document_id TEXT,
                    position INTEGER
                );
                CREATE TABLE source_provenance (
                    document_id TEXT,
                    verification_status TEXT,
                    authority TEXT,
                    jurisdiction TEXT,
                    official_url TEXT,
                    source_type TEXT
                );
                INSERT INTO evidence_documents
                VALUES ('verified-doc', 'case-a', 'official.pdf');
                INSERT INTO evidence_documents
                VALUES ('synthetic-doc', 'case-a', 'synthetic.txt');
                INSERT INTO evidence_passages
                VALUES ('passage-1', 'verified-doc', 1);
                INSERT INTO evidence_passages
                VALUES ('passage-2', 'synthetic-doc', 1);
                INSERT INTO source_provenance
                VALUES (
                    'verified-doc', 'verified', 'Official Authority',
                    'UAE', 'https://example.gov/policy', 'policy'
                );
            """)

    def valid(self, citations):
        return investigation.cached_evidence_citations_valid(
            "case-a",
            {"findings": [{"citations": citations}]}
        )

    def test_verified_citation_accepted(self):
        self.assertTrue(self.valid(["verified-doc#p1"]))

    def test_synthetic_citation_rejected(self):
        self.assertFalse(self.valid(["synthetic-doc#p1"]))

    def test_mixed_verified_and_synthetic_rejected(self):
        self.assertFalse(
            self.valid(["verified-doc#p1", "synthetic-doc#p1"])
        )

    def test_missing_passage_rejected(self):
        self.assertFalse(self.valid(["verified-doc#p999"]))

    def test_malformed_citation_rejected(self):
        self.assertFalse(self.valid(["invalid-reference"]))

    def test_citation_free_finding_rejected(self):
        self.assertFalse(self.valid([]))

    def test_empty_findings_rejected(self):
        self.assertFalse(
            investigation.cached_evidence_citations_valid(
                "case-a", {"findings": []}
            )
        )

    def test_revoked_source_rejected(self):
        with sqlite3.connect(investigation.DB_PATH) as db:
            db.execute("""
                UPDATE source_provenance
                SET verification_status='rejected'
                WHERE document_id='verified-doc'
            """)
        self.assertFalse(self.valid(["verified-doc#p1"]))

    def test_other_case_source_rejected(self):
        self.assertFalse(
            investigation.cached_evidence_citations_valid(
                "case-b",
                {"findings": [{"citations": ["verified-doc#p1"]}]}
            )
        )


if __name__ == "__main__":
    unittest.main()
