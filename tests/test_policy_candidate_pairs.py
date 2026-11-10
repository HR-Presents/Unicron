import unittest

from backend.app.grounded_policy import generate_draft


MATRIX = {
    "jurisdictions": [
        {
            "jurisdiction": "EU",
            "evidence": [
                {"citation": "EU#1", "verbatim_excerpt": "Data security measures."},
                {"citation": "EU#2", "verbatim_excerpt": "Data retention safeguards."},
            ],
        },
        {
            "jurisdiction": "UAE",
            "evidence": [
                {"citation": "UAE#1", "verbatim_excerpt": "Personal data security."},
                {"citation": "UAE#2", "verbatim_excerpt": "Data retention controls."},
            ],
        },
    ]
}


class CandidatePairTests(unittest.TestCase):
    def test_rejects_unselected_citation_pair(self):
        calls = []

        def model_call(system, context, schema, max_tokens):
            calls.append(context)
            return {
                "comparisons": [],
                "recommendation_drafts": [{
                    "action": "Request a qualified assessment of retention safeguards.",
                    "citations": ["EU#2", "UAE#2"],
                    "rationale": "The evidence requires jurisdiction-specific review.",
                }],
                "unresolved_questions": [],
            }

        candidates = [{"citations": ["EU#1", "UAE#1"]}]

        with self.assertRaises(ValueError):
            generate_draft(MATRIX, model_call, candidates=candidates)

        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0]["valid_cross_jurisdiction_citation_pairs"],
            [["EU#1", "UAE#1"]],
        )

    def test_no_candidates_abstains_without_model_call(self):
        def unexpected_call(*args, **kwargs):
            self.fail("Model must not be called")

        result = generate_draft(
            MATRIX,
            unexpected_call,
            candidates=[],
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
