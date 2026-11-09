"""Bounded, deterministic research planning for UNICRON cases.

Planning produces search queries, not evidence or policy conclusions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


MAX_QUERIES = 6
MAX_QUERY_LENGTH = 180

STOPWORDS = frozenset({
    "about", "after", "also", "among", "and", "are",
    "been", "between", "case", "could", "from", "have",
    "into", "more", "need", "other", "over", "should",
    "that", "their", "them", "there", "these", "this",
    "through", "under", "using", "what", "when",
    "where", "which", "while", "with", "would",
})


@dataclass(frozen=True)
class ResearchQuery:
    query: str
    purpose: str
    jurisdiction: str


def _keywords(value: object, limit: int = 12) -> list[str]:
    text = str(value or "").casefold()
    tokens = re.findall(r"[^\W_][\w-]{2,}", text, re.UNICODE)

    result = []
    seen = set()

    for token in tokens:
        if token in STOPWORDS or token in seen:
            continue

        seen.add(token)
        result.append(token)

        if len(result) >= limit:
            break

    return result


def plan_research(
    case: Mapping[str, object],
    *,
    max_queries: int = MAX_QUERIES,
) -> list[ResearchQuery]:
    """Produce bounded queries from user-supplied case information."""
    if not 1 <= max_queries <= MAX_QUERIES:
        raise ValueError("max_queries must be between 1 and 6")

    title = _keywords(case.get("title"), 10)
    summary = _keywords(case.get("summary"), 8)
    domain = _keywords(case.get("domain"), 4)

    terms = list(dict.fromkeys(title + domain + summary))

    if not terms:
        return []

    subject = " ".join(terms[:10])

    candidates = [
        (
            f"{subject} UAE government policy regulation",
            "Identify UAE policy and regulatory context",
            "United Arab Emirates",
        ),
        (
            f"{subject} UAE official government guidance",
            "Locate official implementation guidance",
            "United Arab Emirates",
        ),
        (
            f"{subject} international policy comparison",
            "Identify comparable international approaches",
            "International",
        ),
        (
            f"{subject} international standards framework",
            "Locate relevant standards and frameworks",
            "International",
        ),
        (
            f"{subject} implementation risks governance",
            "Investigate governance and implementation risks",
            "Cross-jurisdiction",
        ),
        (
            f"{subject} evidence evaluation research",
            "Identify research and evaluation evidence",
            "Cross-jurisdiction",
        ),
    ]

    result = []
    seen = set()

    for query, purpose, jurisdiction in candidates:
        query = query[:MAX_QUERY_LENGTH].strip()

        if query.casefold() in seen:
            continue

        seen.add(query.casefold())
        result.append(
            ResearchQuery(
                query=query,
                purpose=purpose,
                jurisdiction=jurisdiction,
            )
        )

        if len(result) >= max_queries:
            break

    return result
