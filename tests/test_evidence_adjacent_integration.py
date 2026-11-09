"""End-to-end adjacent-evidence citation regression tests."""

import json
import sqlite3

from backend.app import evidence


def test_neighbor_citation_survives_analysis_and_persistence(
    tmp_path, monkeypatch
):
    database = tmp_path / "evidence-test.sqlite3"

    with sqlite3.connect(database) as con:
        con.executescript("""
            CREATE TABLE cases (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT
            );
            CREATE TABLE evidence_documents (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                filename TEXT
            );
            CREATE TABLE evidence_passages (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                position INTEGER,
                content TEXT
            );
            CREATE TABLE evidence_runs (
                id TEXT,
                case_id TEXT,
                model TEXT,
                result_json TEXT,
                excerpts_json TEXT,
                created_at TEXT
            );
            CREATE TABLE audit (
                id TEXT,
                case_id TEXT,
                action TEXT,
                detail TEXT,
                created_at TEXT
            );
        """)

        shared = "verified policy evidence " * 6

        con.execute(
            "INSERT INTO cases VALUES (?,?,?)",
            ("case-1", "Healthcare policy", "Patient safety"),
        )
        con.execute(
            "INSERT INTO evidence_documents VALUES (?,?,?)",
            ("doc-1", "case-1", "healthcare-policy.pdf"),
        )
        con.executemany(
            "INSERT INTO evidence_passages VALUES (?,?,?,?)",
            [
                (
                    "passage-1", "doc-1", 1,
                    "Healthcare patient safety " + shared,
                ),
                (
                    "passage-2", "doc-1", 2,
                    shared + "requires documented clinical oversight.",
                ),
            ],
        )

    monkeypatch.setattr(evidence, "DB_PATH", str(database))

    def fake_completion(payload, timeout):
        request = json.loads(
            payload["messages"][1]["content"].split("\n/no_think")[0]
        )
        excerpts = request["excerpts"]

        assert any(
            "doc-1#p2" in excerpt["citations"]
            for excerpt in excerpts
        )

        return {
            "model": "mock-llm",
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps({
                        "findings": [{
                            "statement": (
                                "Documented clinical oversight "
                                "supports healthcare policy."
                            ),
                            "citations": ["doc-1#p2"],
                        }],
                        "gaps": [],
                        "contradictions": [],
                        "recommended_checks": [],
                    })
                },
            }],
        }

    monkeypatch.setattr(evidence, "completion", fake_completion)

    response = evidence.analyze_evidence("case-1")

    assert response["human_review_required"] is True
    assert response["model"] == "mock-llm"
    assert response["result"]["findings"][0]["citations"] == [
        "doc-1#p2"
    ]

    with sqlite3.connect(database) as con:
        stored = con.execute(
            "SELECT result_json, excerpts_json FROM evidence_runs"
        ).fetchone()

        assert stored is not None

        saved_result = json.loads(stored[0])
        saved_excerpts = json.loads(stored[1])

        assert saved_result["findings"][0]["citations"] == [
            "doc-1#p2"
        ]
        assert any(
            "doc-1#p2" in excerpt["citations"]
            for excerpt in saved_excerpts
        )



def test_reconstructed_excerpt_preserves_visible_neighbor_context(
    tmp_path, monkeypatch
):
    database = tmp_path / "truncation-test.sqlite3"

    with sqlite3.connect(database) as con:
        con.executescript("""
            CREATE TABLE cases (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT
            );
            CREATE TABLE evidence_documents (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                filename TEXT
            );
            CREATE TABLE evidence_passages (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                position INTEGER,
                content TEXT
            );
            CREATE TABLE evidence_runs (
                id TEXT,
                case_id TEXT,
                model TEXT,
                result_json TEXT,
                excerpts_json TEXT,
                created_at TEXT
            );
            CREATE TABLE audit (
                id TEXT,
                case_id TEXT,
                action TEXT,
                detail TEXT,
                created_at TEXT
            );
        """)

        overlap = "verified policy evidence " * 6
        padding = "Healthcare patient safety oversight. " * 12

        con.execute(
            "INSERT INTO cases VALUES (?,?,?)",
            ("case-2", "Healthcare policy", "Patient safety"),
        )
        con.execute(
            "INSERT INTO evidence_documents VALUES (?,?,?)",
            ("doc-2", "case-2", "healthcare-policy.pdf"),
        )
        con.executemany(
            "INSERT INTO evidence_passages VALUES (?,?,?,?)",
            [
                (
                    "passage-1", "doc-2", 1,
                    padding + overlap,
                ),
                (
                    "passage-2", "doc-2", 2,
                    overlap + "CLINICAL_OVERSIGHT_VERIFICATION_MARKER",
                ),
            ],
        )

    monkeypatch.setattr(evidence, "DB_PATH", str(database))

    def fake_completion(payload, timeout):
        request = json.loads(
            payload["messages"][1]["content"].split("\n/no_think")[0]
        )

        reconstructed = [
            excerpt for excerpt in request["excerpts"]
            if len(excerpt["citations"]) > 1
        ]

        assert reconstructed, "Expected adjacent-passage reconstruction"
        assert any(
            "CLINICAL_OVERSIGHT_VERIFICATION_MARKER" in excerpt["text"]
            for excerpt in reconstructed
        ), "Reconstructed neighbor evidence was truncated"

        return {
            "model": "mock-llm",
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps({
                        "findings": [],
                        "gaps": [],
                        "contradictions": [],
                        "recommended_checks": [],
                    })
                },
            }],
        }

    monkeypatch.setattr(evidence, "completion", fake_completion)

    response = evidence.analyze_evidence("case-2")
    assert response["human_review_required"] is True



def test_claim_citing_wrong_neighbor_is_flagged(tmp_path, monkeypatch):
    database = tmp_path / "wrong-citation.sqlite3"

    with sqlite3.connect(database) as con:
        con.executescript("""
            CREATE TABLE cases (
                id TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT
            );
            CREATE TABLE evidence_documents (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                filename TEXT
            );
            CREATE TABLE evidence_passages (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                position INTEGER,
                content TEXT
            );
            CREATE TABLE evidence_runs (
                id TEXT,
                case_id TEXT,
                model TEXT,
                result_json TEXT,
                excerpts_json TEXT,
                created_at TEXT
            );
            CREATE TABLE audit (
                id TEXT,
                case_id TEXT,
                action TEXT,
                detail TEXT,
                created_at TEXT
            );
        """)

        overlap = "verified policy evidence " * 6

        con.execute(
            "INSERT INTO cases VALUES (?,?,?)",
            ("case-3", "Healthcare policy", "Patient safety"),
        )
        con.execute(
            "INSERT INTO evidence_documents VALUES (?,?,?)",
            ("doc-3", "case-3", "healthcare-policy.pdf"),
        )
        con.executemany(
            "INSERT INTO evidence_passages VALUES (?,?,?,?)",
            [
                (
                    "passage-1", "doc-3", 1,
                    "Healthcare patient safety " + overlap,
                ),
                (
                    "passage-2", "doc-3", 2,
                    overlap + (
                        "Clinical oversight requires documented "
                        "patient safety verification."
                    ),
                ),
            ],
        )

    monkeypatch.setattr(evidence, "DB_PATH", str(database))

    def fake_completion(payload, timeout):
        request = json.loads(
            payload["messages"][1]["content"].split("\n/no_think")[0]
        )
        assert any(
            len(excerpt["citations"]) > 1
            for excerpt in request["excerpts"]
        )

        return {
            "model": "mock-llm",
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps({
                        "findings": [{
                            "statement": (
                                "Clinical oversight requires documented "
                                "patient safety verification."
                            ),
                            "citations": ["doc-3#p1"],
                        }],
                        "gaps": [],
                        "contradictions": [],
                        "recommended_checks": [],
                    })
                },
            }],
        }

    monkeypatch.setattr(evidence, "completion", fake_completion)

    response = evidence.analyze_evidence("case-3")

    assert response["result"]["findings"] == []
    assert any(
        finding["citations"] == ["doc-3#p1"]
        for finding in response["result"]["flagged_findings"]
    )
