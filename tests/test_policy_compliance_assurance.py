import unittest

from backend.app.grounded_policy import validate_draft


class ComplianceAssuranceTests(unittest.TestCase):
    def test_unsupported_compliance_assurance_is_flagged(self):
        matrix = {
            "jurisdictions": [
                {
                    "jurisdiction": "European Union",
                    "evidence": [{
                        "citation": "EU#p1",
                        "verbatim_excerpt": (
                            "Special categories of personal data "
                            "require safeguards."
                        ),
                    }],
                },
                {
                    "jurisdiction": "United Arab Emirates",
                    "evidence": [{
                        "citation": "UAE#p1",
                        "verbatim_excerpt": (
                            "Personal data requires appropriate "
                            "security measures."
                        ),
                    }],
                },
            ]
        }

        raw = {
            "comparisons": [],
            "recommendation_drafts": [{
                "action": (
                    "Implement a framework ensuring compliance "
                    "with both EU and UAE regulations."
                ),
                "citations": ["EU#p1", "UAE#p1"],
                "rationale": (
                    "This action ensures compliance with "
                    "both regulatory frameworks."
                ),
            }],
            "unresolved_questions": [],
        }

        result = validate_draft(raw, matrix)

        codes = {
            flag["code"]
            for flag in result["claim_risk_flags"]
        }

        self.assertIn("unproven_compliance_assurance", codes)
        self.assertEqual(result["approved_policy_findings"], [])
        self.assertFalse(result["automated_approval_permitted"])
        self.assertTrue(result["human_review_required"])


if __name__ == "__main__":
    unittest.main()
