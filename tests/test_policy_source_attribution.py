import unittest

from backend.app.grounded_policy import generate_draft, verify_draft_claims


MATRIX = {
    "jurisdictions": [
        {
            "jurisdiction": "EU",
            "evidence": [{
                "citation": "EU#1",
                "verbatim_excerpt": "Providers shall establish risk management measures.",
                "provenance": {
                    "document_title": "EU Artificial Intelligence Act",
                    "official_url": "https://eur-lex.europa.eu/",
                },
            }],
        },
        {
            "jurisdiction": "UAE",
            "evidence": [{
                "citation": "UAE#1",
                "verbatim_excerpt": "Personal data protection measures are described.",
                "provenance": {
                    "document_title": "UAE Personal Data Protection Law",
                    "official_url": "https://uaelegislation.gov.ae/",
                },
            }],
        },
    ]
}


class SourceAttributionTests(unittest.TestCase):

    def test_drafting_preserves_source_metadata(self):
        contexts = []

        def model_call(system, context, schema, max_tokens):
            contexts.append(context)
            return {
                "comparisons": [],
                "recommendation_drafts": [],
                "unresolved_questions": [],
            }

        result = generate_draft(MATRIX, model_call)

        self.assertIsNotNone(result)

        self.assertEqual(
            contexts[0]["evidence"][0]["provenance"]["document_title"],
            "EU Artificial Intelligence Act",
        )
        self.assertEqual(
            result["evidence"][1]["provenance"]["official_url"],
            "https://uaelegislation.gov.ae/",
        )

    def test_verifier_preserves_source_metadata(self):

        def draft_model(system, context, schema, max_tokens):
            return {
                "comparisons": [{
                    "observation": (
                        "The excerpts describe different subjects "
                        "that require qualified review."
                    ),
                    "citations": ["EU#1", "UAE#1"],
                    "classification": "requires_review",
                }],
                "recommendation_drafts": [],
                "unresolved_questions": [],
            }

        draft = generate_draft(MATRIX, draft_model)
        contexts = []

        def verifier(system, context, schema, max_tokens):
            contexts.append(context)
            return {
                "assessments": [{
                    "claim_index": 0,
                    "verdict": "insufficient_evidence",
                    "reason": "The excerpts do not establish legal comparability.",
                }]
            }

        verify_draft_claims(draft, verifier)

        cited = contexts[0]["claims"][0]["cited_excerpts"]

        self.assertEqual(
            cited[0]["provenance"]["document_title"],
            "EU Artificial Intelligence Act",
        )
        self.assertEqual(
            cited[1]["provenance"]["official_url"],
            "https://uaelegislation.gov.ae/",
        )


if __name__ == "__main__":
    unittest.main()
