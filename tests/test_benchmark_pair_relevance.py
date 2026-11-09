import unittest

from backend.app.policy_intelligence import _comparison_draft


class BenchmarkPairRelevanceTests(unittest.TestCase):
    def test_substantive_pair_outranks_generic_regulatory_overlap(self):
        matrix = {
            "jurisdictions": [
                {
                    "jurisdiction": "European Union",
                    "evidence": [
                        {
                            "citation": "EU#generic",
                            "verbatim_excerpt": (
                                "The regulation describes administrative "
                                "procedures and general requirements."
                            ),
                        },
                        {
                            "citation": "EU#security",
                            "verbatim_excerpt": (
                                "Personal data security measures include "
                                "encryption and access controls."
                            ),
                        },
                    ],
                },
                {
                    "jurisdiction": "United Arab Emirates",
                    "evidence": [
                        {
                            "citation": "UAE#generic",
                            "verbatim_excerpt": (
                                "The regulation establishes general "
                                "administrative requirements."
                            ),
                        },
                        {
                            "citation": "UAE#security",
                            "verbatim_excerpt": (
                                "Personal data security safeguards include "
                                "encryption and access controls."
                            ),
                        },
                    ],
                },
            ]
        }

        result = _comparison_draft(matrix)

        self.assertEqual(result["status"], "review_required")
        self.assertEqual(
            result["candidates"][0]["citations"],
            ["EU#security", "UAE#security"],
        )
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["policy_recommendation_drafts"], [])


if __name__ == "__main__":
    unittest.main()


def test_technical_security_pair_outranks_administrative_overlap():
    matrix = {
        "jurisdictions": [
            {
                "jurisdiction": "EU",
                "evidence": [
                    {
                        "citation": "EU#administrative",
                        "verbatim_excerpt": (
                            "Regulation administrative procedures general requirements "
                            "documentation reporting registration notification "
                            "assessment authority."
                        ),
                    },
                    {
                        "citation": "EU#encryption",
                        "verbatim_excerpt": (
                            "Encryption safeguards protect sensitive personal "
                            "data against unauthorized access."
                        ),
                    },
                ],
            },
            {
                "jurisdiction": "UAE",
                "evidence": [
                    {
                        "citation": "UAE#administrative",
                        "verbatim_excerpt": (
                            "Regulation administrative procedures general requirements "
                            "documentation reporting registration notification "
                            "assessment authority."
                        ),
                    },
                    {
                        "citation": "UAE#encryption",
                        "verbatim_excerpt": (
                            "Encryption safeguards protect personal data "
                            "against unauthorized disclosure."
                        ),
                    },
                ],
            },
        ]
    }

    result = _comparison_draft(matrix)

    assert result["candidates"][0]["citations"] == [
        "EU#encryption",
        "UAE#encryption",
    ]
    assert result["human_review_required"] is True
