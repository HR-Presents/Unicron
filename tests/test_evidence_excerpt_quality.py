"""Evidence excerpt quality and citation-preserving text extraction."""
import unittest

from backend.app.evidence import prepare_evidence_excerpt


class EvidenceExcerptQualityTests(unittest.TestCase):

    def test_complete_sentence_is_preserved(self):
        content = (
            "High-risk AI systems shall use appropriate data governance "
            "and management practices."
        )
        self.assertEqual(
            prepare_evidence_excerpt(content),
            content,
        )

    def test_does_not_end_mid_sentence(self):
        content = (
            "High-risk AI systems shall use appropriate data governance "
            "and management practices. "
            "The following requirements describe additional safeguards "
            "for the deployment and monitoring of such systems."
        )
        excerpt = prepare_evidence_excerpt(content, max_chars=110)
        self.assertTrue(excerpt.endswith("."))
        self.assertLessEqual(len(excerpt), 110)

    def test_prefers_complete_sentence_after_fragment(self):
        content = (
            "ural persons to whom oversight is assigned. "
            "Operators shall understand the limitations of the AI system."
        )
        excerpt = prepare_evidence_excerpt(content, max_chars=160)
        self.assertIn(
            "Operators shall understand the limitations",
            excerpt,
        )
        self.assertNotIn("ural persons", excerpt)

    def test_removes_testing_header(self):
        content = (
            "SOURCE EXCERPTS FOR UNICRON TESTING — NOT ORIGINAL\n"
            "High-risk AI systems shall be monitored."
        )
        excerpt = prepare_evidence_excerpt(content)
        self.assertNotIn("SOURCE EXCERPTS", excerpt)
        self.assertIn("High-risk AI systems", excerpt)



    def test_numbered_legal_paragraph_is_not_a_sentence(self):
        content = (
            "Article 10\n"
            "1. High-risk AI systems shall use appropriate data governance.\n"
            "2. Training and testing datasets shall be reviewed for quality "
            "and potential bias before deployment."
        )
        self.assertIn(chr(10), content)
        self.assertNotIn(chr(92) + "n", content)
        excerpt = prepare_evidence_excerpt(content, max_chars=90)
        self.assertNotEqual(excerpt, "")
        self.assertNotEqual(excerpt.rstrip()[-2:], "2.")
        self.assertTrue(excerpt.endswith("governance."))

    def test_incomplete_trailing_legal_clause_is_excluded(self):
        content = (
            "5. For high-risk AI systems, providers shall establish "
            "appropriate human oversight measures and ensure that "
            "the responsible persons have the necessary"
        )
        excerpt = prepare_evidence_excerpt(content, max_chars=420)
        self.assertEqual(excerpt, "")

    def test_no_empty_excerpts_in_citation_allowlist(self):
        from backend.app.evidence import build_usable_excerpts

        selected = [
            {
                "document_id": "doc-a",
                "position": 1,
                "filename": "source.txt",
                "content": "Incomplete regulatory provision without a terminator",
            },
            {
                "document_id": "doc-a",
                "position": 2,
                "filename": "source.txt",
                "content": "Operators shall monitor AI system performance.",
            },
        ]

        excerpts = build_usable_excerpts(selected)

        self.assertEqual(len(excerpts), 1)
        self.assertEqual(excerpts[0]["citation"], "doc-a#p2")
        self.assertTrue(excerpts[0]["text"])

    def test_empty_input_is_safe(self):
        self.assertEqual(prepare_evidence_excerpt(""), "")


if __name__ == "__main__":
    unittest.main()
