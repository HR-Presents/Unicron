"""Policy and cross-jurisdiction grounding regression suite."""
import unittest

from backend.app.policy_intelligence import policy_stage, benchmark_stage
from backend.app.grounded_policy import validate_draft

CASE = {"title": "Public service continuity", "summary": "Emergency notification continuity across agencies."}


def passage(citation, jurisdiction, source_type="benchmark", verified="verified", url="https://example.org/policy"):
    return {
        "citation": citation, "jurisdiction": jurisdiction, "source_type": source_type,
        "verification_status": verified, "official_url": url,
        "text": "Agencies publish emergency notification continuity guidance for public service operations, including communication procedures, responsible personnel, escalation arrangements, and coordination during service disruptions.",
        "source_note": source_type, "filename": "source.pdf", "document_id": citation,
    }


MATRIX = {"jurisdictions": [
    {"jurisdiction": "UAE", "evidence": [{"citation": "uae#p1", "verbatim_excerpt": "Agencies publish guidance."}]},
    {"jurisdiction": "Singapore", "evidence": [{"citation": "sg#p1", "verbatim_excerpt": "Offices publish guidance."}]},
]}


def raw(citations=None, classification="requires_review"):
    return {
        "comparisons": [{"observation": "Both excerpts describe publishing agency guidance.",
                         "citations": citations or ["uae#p1", "sg#p1"],
                         "classification": classification}],
        "recommendation_drafts": [], "unresolved_questions": [],
    }


class PolicyGroundingBatchTests(unittest.TestCase):
    def test_unverified_policy_is_not_eligible(self):
        stage = policy_stage([passage("a", "UAE", "policy", "pending")], CASE)
        self.assertEqual(stage["status"], "source_required")
        self.assertIsNone(stage["result"]["policy_conclusion"])

    def test_policy_requires_official_url(self):
        stage = policy_stage([passage("a", "UAE", "policy", url="")], CASE)
        self.assertEqual(stage["status"], "source_required")

    def test_verified_policy_is_still_review_required(self):
        stage = policy_stage([passage("a", "UAE", "policy")], CASE)
        self.assertEqual(stage["status"], "review_required")
        self.assertIsNone(stage["result"]["policy_conclusion"])

    def test_one_benchmark_jurisdiction_is_insufficient(self):
        stage = benchmark_stage([passage("a", "UAE"), passage("b", "uae")], CASE)
        self.assertEqual(stage["status"], "source_required")
        self.assertIsNone(stage["result"]["evidence_matrix"])

    def test_two_verified_jurisdictions_remain_advisory(self):
        stage = benchmark_stage([passage("a", "UAE"), passage("b", "Singapore")], CASE)
        self.assertEqual(stage["status"], "review_required")
        matrix = stage["result"]["evidence_matrix"]
        self.assertTrue(matrix["human_review_required"])
        self.assertEqual(matrix["legal_applicability"], "not_established")
        self.assertIsNone(stage["result"]["comparison"])

    def test_unverified_second_jurisdiction_is_not_counted(self):
        stage = benchmark_stage([passage("a", "UAE"), passage("b", "Singapore", verified="pending")], CASE)
        self.assertEqual(stage["status"], "source_required")

    def test_unknown_citation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported citation"):
            validate_draft(raw(["uae#p1", "unknown#p1"]), MATRIX)

    def test_same_jurisdiction_citations_are_rejected(self):
        matrix = {"jurisdictions": [
            {"jurisdiction": "UAE", "evidence": [
                {"citation": "uae#p1", "verbatim_excerpt": "Guidance one."},
                {"citation": "uae#p2", "verbatim_excerpt": "Guidance two."}]}]}
        with self.assertRaisesRegex(ValueError, "two distinct jurisdictions"):
            validate_draft(raw(["uae#p1", "uae#p2"]), matrix)

    def test_repeated_citation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Repeated citation"):
            validate_draft(raw(["uae#p1", "uae#p1"]), MATRIX)

    def test_unsupported_classification_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported comparison classification"):
            validate_draft(raw(classification="verified_legal_equivalence"), MATRIX)

    def test_valid_draft_never_auto_approves(self):
        result = validate_draft(raw(), MATRIX)
        self.assertEqual(result["status"], "review_required")
        self.assertFalse(result["automated_approval_permitted"])
        self.assertEqual(result["approved_policy_findings"], [])
        self.assertTrue(result["human_review_required"])


if __name__ == "__main__":
    unittest.main()
