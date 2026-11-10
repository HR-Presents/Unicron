"""Tests for provenance-preserving evidence reconstruction."""

import unittest

from backend.app import evidence


class EvidenceReconstructionTests(unittest.TestCase):

    def test_exact_overlap_reconstruction(self):
        passages = [
            {
                "document_id": "doc-a",
                "position": 1,
                "content": "Providers shall ensure human oversight.",
            },
            {
                "document_id": "doc-a",
                "position": 2,
                "content": "human oversight. Operators shall monitor outputs.",
            },
        ]

        result = evidence.reconstruct_adjacent_passages(
            passages, min_overlap=16
        )

        self.assertEqual(
            result["text"],
            "Providers shall ensure human oversight. "
            "Operators shall monitor outputs.",
        )

    def test_rejects_unverified_overlap(self):
        passages = [
            {
                "document_id": "doc-a",
                "position": 1,
                "content": "First unrelated passage.",
            },
            {
                "document_id": "doc-a",
                "position": 2,
                "content": "Second unrelated passage.",
            },
        ]

        with self.assertRaises(ValueError):
            evidence.reconstruct_adjacent_passages(
                passages, min_overlap=16
            )

    def test_rejects_cross_document_join(self):
        passages = [
            {
                "document_id": "doc-a",
                "position": 1,
                "content": "Providers shall ensure human oversight.",
            },
            {
                "document_id": "doc-b",
                "position": 2,
                "content": "human oversight. Operators shall monitor outputs.",
            },
        ]

        with self.assertRaises(ValueError):
            evidence.reconstruct_adjacent_passages(
                passages, min_overlap=16
            )

    def test_preserves_all_contributing_citations(self):
        passages = [
            {
                "document_id": "doc-a",
                "position": 1,
                "content": "Providers shall ensure human oversight.",
            },
            {
                "document_id": "doc-a",
                "position": 2,
                "content": "human oversight. Operators shall monitor outputs.",
            },
        ]

        result = evidence.reconstruct_adjacent_passages(
            passages, min_overlap=16
        )

        self.assertEqual(
            result["citations"],
            ["doc-a#p1", "doc-a#p2"],
        )

    def test_rejects_nonadjacent_positions(self):
        passages = [
            {
                "document_id": "doc-a",
                "position": 1,
                "content": "Providers shall ensure human oversight.",
            },
            {
                "document_id": "doc-a",
                "position": 3,
                "content": "human oversight. Operators shall monitor outputs.",
            },
        ]

        with self.assertRaises(ValueError):
            evidence.reconstruct_adjacent_passages(
                passages, min_overlap=16
            )


if __name__ == "__main__":
    unittest.main()
