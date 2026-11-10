import unittest
from backend.app.retrieval_rank import rank_passages


def passage(doc, text, position=1):
    return {
        "document_id": doc,
        "position": position,
        "content": text,
        "filename": f"{doc}.txt",
        "source_note": "",
    }


class RetrievalRankTests(unittest.TestCase):
    def test_whole_words_not_substrings(self):
        rows = [
            passage("a", "waterfall planning"),
            passage("b", "water planning"),
        ]
        result = rank_passages(rows, ["water"])
        self.assertEqual(
            [row["document_id"] for row in result], ["b"]
        )

    def test_query_coverage_beats_keyword_stuffing(self):
        rows = [
            passage("a", "water " * 100),
            passage("b", "water infrastructure continuity"),
        ]
        result = rank_passages(
            rows, ["water", "infrastructure", "continuity"]
        )
        self.assertEqual(result[0]["document_id"], "b")

    def test_citation_preserved(self):
        result = rank_passages(
            [passage("doc-123", "policy evidence", 7)],
            ["policy"],
        )
        self.assertEqual(
            result[0]["citation"], "doc-123#p7"
        )

    def test_no_match(self):
        self.assertEqual(
            rank_passages(
                [passage("a", "unrelated")], ["regulation"]
            ),
            [],
        )

    def test_deterministic(self):
        rows = [
            passage("b", "policy"),
            passage("a", "policy"),
        ]
        self.assertEqual(
            rank_passages(rows, ["policy"]),
            rank_passages(list(reversed(rows)), ["policy"]),
        )


if __name__ == "__main__":
    unittest.main()
