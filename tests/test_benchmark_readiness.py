import unittest

from backend.app.policy_intelligence import benchmark_stage


CASE = {
    "title": "Municipal service continuity",
    "summary": "Residents require timely public service notices.",
}


def passage(jurisdiction, citation, text, status="verified"):
    return {
        "jurisdiction": jurisdiction,
        "citation": citation,
        "document_id": citation.split("#")[0],
        "text": text,
        "source_type": "benchmark",
        "verification_status": status,
        "official_url": "https://example.gov/policy",
        "filename": "fixture.txt",
        "authority": "Test Authority",
        "document_title": "Test fixture",
        "source_note": "",
    }


SUBSTANTIVE = (
    "Municipal authorities maintain documented service continuity "
    "arrangements and provide timely public notices to affected "
    "residents during infrastructure interruptions."
)


class BenchmarkReadinessTests(unittest.TestCase):
    def test_two_verified_but_one_empty_is_not_ready(self):
        result = benchmark_stage([
            passage("UAE", "a#p1", SUBSTANTIVE),
            passage("Singapore", "b#p1", "Short fragment"),
        ], CASE)

        self.assertEqual(result["status"], "source_required")
        self.assertIsNone(result["result"]["evidence_matrix"])
        self.assertIsNone(result["result"]["comparison_draft"])

    def test_two_substantive_jurisdictions_ready(self):
        result = benchmark_stage([
            passage("UAE", "a#p1", SUBSTANTIVE),
            passage(
                "Singapore", "b#p1",
                "Government agencies maintain documented emergency "
                "continuity plans and provide public notifications "
                "during essential infrastructure disruptions."
            ),
        ], CASE)

        self.assertEqual(result["status"], "review_required")
        self.assertEqual(
            len(result["result"]["jurisdiction_evidence"]), 2
        )

    def test_rejected_source_cannot_make_ready(self):
        result = benchmark_stage([
            passage("UAE", "a#p1", SUBSTANTIVE),
            passage("Singapore", "b#p1", SUBSTANTIVE, "rejected"),
        ], CASE)

        self.assertEqual(result["status"], "source_required")

    def test_global_guidance_not_counted_as_jurisdiction(self):
        result = benchmark_stage([
            passage("UAE", "a#p1", SUBSTANTIVE),
            passage("Global", "b#p1", SUBSTANTIVE),
        ], CASE)

        self.assertEqual(result["status"], "source_required")


if __name__ == "__main__":
    unittest.main()
