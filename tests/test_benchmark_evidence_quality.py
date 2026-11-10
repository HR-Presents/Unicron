import unittest

from backend.app.policy_intelligence import _benchmark_rank


class BenchmarkEvidenceRankingTests(unittest.TestCase):
    def test_discards_wrapper_and_retains_substantive_text(self):
        passages = [
            {
                "citation": "eu#p1",
                "text": (
                    "SOURCE EXCERPTS FOR UNICRON TESTING — NOT THE COMPLETE ORIGINAL DOCUMENT\n"
                    "Human reviewer must compare each excerpt against the original PDF.\n"
                    "===== ORIGINAL PDF PAGE 56 =====\n"
                    "Providers shall document oversight arrangements and ensure that designated "
                    "personnel can monitor system operation, detect anomalies, and intervene "
                    "when appropriate to protect affected persons."
                ),
            }
        ]
        ranked = _benchmark_rank(passages, "oversight monitor", limit=12)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0][1], "eu#p1")
        self.assertNotIn("Human reviewer must compare", ranked[0][2])
        self.assertIn("monitor system operation", ranked[0][2])

    def test_preserves_distinct_source_citations(self):
        passages = [
            {"citation": "eu#p27", "text": "Human oversight measures must be established so that qualified operators can monitor an automated system and respond to unexpected behavior."},
            {"citation": "uae#p50", "text": "Security measures include encryption and continuous evaluation of the effectiveness of safeguards for personal data processing systems."},
        ]
        ranked = _benchmark_rank(passages, "oversight security processing")
        self.assertEqual({r[1] for r in ranked}, {"eu#p27", "uae#p50"})

    def test_rejects_short_fragments(self):
        ranked = _benchmark_rank([{"citation": "x#p1", "text": "f Personal Data 23"}], "data")
        self.assertEqual(ranked, [])


if __name__ == "__main__":
    unittest.main()
