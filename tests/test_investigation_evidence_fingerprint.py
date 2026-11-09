"""Regression tests for investigation evidence-input fingerprinting."""
import sqlite3
import unittest

from backend.app.investigation import evidence_fingerprint


class EvidenceFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE evidence_documents (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                filename TEXT,
                source_note TEXT,
                sha256 TEXT,
                passage_count INTEGER
            );
            CREATE TABLE evidence_passages (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                position INTEGER,
                content TEXT
            );
            CREATE TABLE source_provenance (
                document_id TEXT PRIMARY KEY,
                verification_status TEXT,
                verified_by TEXT,
                verified_at TEXT
            );
            INSERT INTO evidence_documents VALUES
                ('doc1', 'case1', 'policy.pdf', 'policy', 'abc', 1);
            INSERT INTO evidence_passages VALUES
                ('p1', 'doc1', 0, 'Original evidence content');
            INSERT INTO source_provenance VALUES
                ('doc1', 'unverified', NULL, NULL);
        """)

    def fingerprint(self):
        return evidence_fingerprint(self.db, "case1")

    def test_unchanged_evidence_is_stable(self):
        self.assertEqual(self.fingerprint(), self.fingerprint())

    def test_passage_edit_invalidates_fingerprint(self):
        before = self.fingerprint()
        self.db.execute(
            "UPDATE evidence_passages SET content=? WHERE id='p1'",
            ("Updated evidence content",)
        )
        self.assertNotEqual(before, self.fingerprint())

    def test_verification_change_invalidates_fingerprint(self):
        before = self.fingerprint()
        self.db.execute(
            """UPDATE source_provenance
               SET verification_status='verified',
                   verified_by='reviewer'
               WHERE document_id='doc1'"""
        )
        self.assertNotEqual(before, self.fingerprint())

    def test_document_deletion_invalidates_fingerprint(self):
        before = self.fingerprint()
        self.db.execute("DELETE FROM evidence_passages WHERE document_id='doc1'")
        self.db.execute("DELETE FROM source_provenance WHERE document_id='doc1'")
        self.db.execute("DELETE FROM evidence_documents WHERE id='doc1'")
        self.assertNotEqual(before, self.fingerprint())

    def test_document_addition_invalidates_fingerprint(self):
        before = self.fingerprint()
        self.db.execute(
            """INSERT INTO evidence_documents VALUES
               ('doc2', 'case1', 'new.pdf', 'benchmark', 'def', 0)"""
        )
        self.assertNotEqual(before, self.fingerprint())

    def test_other_case_does_not_change_fingerprint(self):
        before = self.fingerprint()
        self.db.execute(
            """INSERT INTO evidence_documents VALUES
               ('other', 'case2', 'other.pdf', 'policy', 'xyz', 0)"""
        )
        self.assertEqual(before, self.fingerprint())

    def test_fingerprint_is_order_independent(self):
        before = self.fingerprint()
        self.db.execute("DELETE FROM evidence_passages WHERE id='p1'")
        self.db.execute(
            """INSERT INTO evidence_passages VALUES
               ('p1', 'doc1', 0, 'Original evidence content')"""
        )
        self.assertEqual(before, self.fingerprint())


if __name__ == "__main__":
    unittest.main()
