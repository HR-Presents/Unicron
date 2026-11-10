import unittest

from backend.app.policy_intelligence import _benchmark_rank


def passage(document, number, text):
    return {
        "document_id": document,
        "citation": f"{document}#p{number}",
        "text": text,
    }


class BenchmarkDiversityTests(unittest.TestCase):
    def test_multiple_documents_represented(self):
        rows = [
            passage(
                "a", i,
                "Public service continuity requires timely resident notices "
                "during essential infrastructure interruptions and documented "
                f"restoration procedure number {i} for municipal operators."
            )
            for i in range(1, 7)
        ]
        rows.append(passage(
            "b", 1,
            "Municipal authorities publish resident notices when essential "
            "services are interrupted and maintain documented restoration "
            "procedures for affected neighborhoods."
        ))

        result = _benchmark_rank(rows, "resident notices restoration", limit=3)
        self.assertEqual(len(result), 3)
        self.assertEqual(
            {row[3]["document_id"] for row in result},
            {"a", "b"},
        )

    def test_exact_duplicate_text_removed(self):
        text = (
            "Public authorities maintain operational continuity plans "
            "and communicate service restoration procedures to residents "
            "during major municipal infrastructure disruptions."
        )
        rows = [
            passage("a", 1, text),
            passage("a", 2, text),
        ]
        result = _benchmark_rank(rows, "continuity restoration", limit=12)
        self.assertEqual(len(result), 1)

    def test_citation_preserved(self):
        result = _benchmark_rank([
            passage(
                "source", 7,
                "Public service continuity policies require operators "
                "to document emergency response arrangements and provide "
                "timely information to affected residents."
            )
        ], "continuity policies")
        self.assertEqual(result[0][1], "source#p7")

    def test_deterministic_selection(self):
        rows = [
            passage(
                "a", 1,
                "Public authorities document emergency continuity "
                "procedures and provide notices to affected residents."
            ),
            passage(
                "b", 2,
                "Municipal authorities maintain continuity plans "
                "and communicate restoration information to residents."
            ),
        ]
        first = _benchmark_rank(rows, "continuity residents")
        second = _benchmark_rank(list(reversed(rows)), "continuity residents")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
