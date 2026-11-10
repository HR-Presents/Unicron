"""Deterministic, bounded lexical ranking for evidence passages.

Ranking is a retrieval signal, not proof of source authenticity or entailment.
"""
import math
import re
from collections import Counter


def _words(value):
    return re.findall(r"[\w]+(?:-[\w]+)*", (value or "").casefold())


def rank_passages(rows, tokens):
    """Return citation-preserving ranked passages with stable tie-breaking."""
    query = list(dict.fromkeys(
        token.casefold() for token in tokens if token
    ))
    if not query:
        return []

    documents = [dict(row) for row in rows]
    frequencies = []
    document_frequency = Counter()

    for document in documents:
        counts = Counter(_words(document["content"]))
        frequencies.append(counts)
        document_frequency.update(
            token for token in query if counts[token] > 0
        )

    total = len(documents)
    ranked = []

    for document, counts in zip(documents, frequencies):
        matched = [token for token in query if counts[token] > 0]
        if not matched:
            continue

        coverage = len(matched) / len(query)
        relevance = sum(
            (1.0 + math.log1p(min(counts[token], 5)))
            * math.log1p(
                (total + 1) / (document_frequency[token] + 1)
            )
            for token in matched
        )

        result = document.copy()
        result["score"] = round(
            relevance + 3.0 * coverage, 6
        )
        result["citation"] = (
            f"{document['document_id']}#p{document['position']}"
        )
        ranked.append(result)

    ranked.sort(
        key=lambda row: (
            -row["score"],
            row["filename"],
            row["position"],
            row["document_id"],
        )
    )
    return ranked
