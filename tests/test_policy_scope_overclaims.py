import unittest

from backend.app.grounded_policy import validate_draft


MATRIX = {
    "jurisdictions": [
        {
            "jurisdiction": "EU",
            "evidence": [{
                "citation": "EU#1",
                "verbatim_excerpt": (
                    "Providers shall establish risk management measures."
                ),
            }],
        },
        {
            "jurisdiction": "UAE",
            "evidence": [{
                "citation": "UAE#1",
                "verbatim_excerpt": (
                    "Personal data protection measures are described."
                ),
            }],
        },
    ]
}


def make_draft(observation=None, action=None):
    comparisons = []
    recommendations = []

    if observation:
        comparisons.append({
            "observation": observation,
            "citations": ["EU#1", "UAE#1"],
            "classification": "requires_review",
        })

    if action:
        recommendations.append({
            "action": action,
            "citations": ["EU#1", "UAE#1"],
            "rationale": (
                "A qualified reviewer must assess applicability."
            ),
        })

    return {
        "comparisons": comparisons,
        "recommendation_drafts": recommendations,
        "unresolved_questions": [],
    }


class PolicyScopeOverclaimTests(unittest.TestCase):

    def test_unproven_legal_conflict_is_flagged(self):
        draft = make_draft(
            observation=(
                "The EU and UAE laws conflict "
                "on their regulatory obligations."
            )
        )

        result = validate_draft(draft, MATRIX)

        codes = {
            flag["code"]
            for flag in result["claim_risk_flags"]
        }

        self.assertIn("unproven_legal_conflict", codes)
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["automated_approval_permitted"])

    def test_unproven_legal_difference_is_flagged(self):
        draft = make_draft(
            observation=(
                "The jurisdictions impose different legal requirements "
                "for artificial intelligence systems."
            )
        )

        result = validate_draft(draft, MATRIX)

        codes = {
            flag["code"]
            for flag in result["claim_risk_flags"]
        }

        self.assertIn("unproven_legal_difference", codes)
        self.assertEqual(
            result["legal_applicability"],
            "not_established",
        )

    def test_compliance_guarantee_is_flagged(self):
        draft = make_draft(
            action=(
                "Implement this framework to ensure compliance "
                "with both jurisdictions."
            )
        )

        result = validate_draft(draft, MATRIX)

        codes = {
            flag["code"]
            for flag in result["claim_risk_flags"]
        }

        self.assertIn("unproven_compliance_assurance", codes)
        self.assertEqual(
            result["approved_policy_findings"],
            [],
        )


if __name__ == "__main__":
    unittest.main()
