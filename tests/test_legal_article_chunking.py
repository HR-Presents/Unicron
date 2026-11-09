import unittest

from backend.app.evidence import chunk_text


class LegalArticleChunkingTests(unittest.TestCase):

    def test_preserves_article_boundary(self):
        article_10 = (
            "Article 10\n"
            "Data and data governance\n"
            + "Training datasets must satisfy quality requirements. " * 13
        )
        article_11 = (
            "\nArticle 11\n"
            "Technical documentation\n"
            + "Providers must maintain technical documentation. " * 13
        )

        chunks = chunk_text(article_10 + article_11)

        for chunk in chunks:
            self.assertFalse(
                "Article 10" in chunk and "Article 11" in chunk,
                "A chunk must not combine two distinct legal articles",
            )

    def test_short_general_text_remains_supported(self):
        chunks = chunk_text(
            "A short general evidence document."
        )
        self.assertEqual(
            chunks,
            ["A short general evidence document."],
        )

    def test_empty_text_is_rejected(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as context:
            chunk_text("   ")

        self.assertEqual(context.exception.status_code, 422)


    def test_oversized_legal_document_is_rejected(self):
        from fastapi import HTTPException

        text = (
            "Article 1\\n" + "A" * 150_000 +
            "\\nArticle 2\\n" + "B" * 150_001
        )

        with self.assertRaises(HTTPException) as context:
            chunk_text(text)

        self.assertEqual(context.exception.status_code, 413)

    def test_uae_article_heading_is_separated(self):
        text = (
            "Article (20)\nPersonal Data Security\n" +
            "Security measures must be maintained. " * 18 +
            "\nArticle (21)\nImpact Assessment\n" +
            "Processing risks must be assessed. " * 18
        )

        chunks = chunk_text(text)

        for chunk in chunks:
            self.assertFalse(
                "Article (20)" in chunk and "Article (21)" in chunk
            )

    def test_long_article_retains_all_text(self):
        text = (
            "Article 10\\n" +
            "Regulatory requirements and safeguards. " * 100
        )

        chunks = chunk_text(text)

        self.assertTrue(chunks)
        self.assertIn("Article 10", chunks[0])
        self.assertIn(
            "safeguards.",
            chunks[-1],
        )


if __name__ == "__main__":
    unittest.main()


def test_article_aware_chunking_preserves_normalized_source_text():
    from backend.app.evidence import chunk_text

    original = (
        "Article 10\n"
        + "Data governance requirements. " * 35
        + "\nArticle 11\n"
        + "Technical documentation requirements. " * 35
    )

    chunks = chunk_text(original)
    normalized_chunks = [" ".join(c.split()) for c in chunks]

    reconstructed = normalized_chunks[0]
    previous_chunk = normalized_chunks[0]

    for chunk in normalized_chunks[1:]:
        overlap = 0

        for size in range(min(len(previous_chunk), len(chunk), 100), 0, -1):
            if previous_chunk.endswith(chunk[:size]):
                overlap = size
                break

        if overlap:
            reconstructed += chunk[overlap:]
        else:
            reconstructed += " " + chunk

        previous_chunk = chunk

    assert reconstructed == " ".join(original.split())
