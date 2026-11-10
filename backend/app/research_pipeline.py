"""Bounded research discovery coordinator.

Discovered URLs are unverified candidates, never approved evidence.
This module does not download documents or modify the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .research_discovery import (
    DiscoveredSource,
    discover_sources,
)
from .research_planner import plan_research


MAX_DISCOVERY_QUERIES = 3
MAX_CANDIDATES = 9


@dataclass(frozen=True)
class ResearchDiscoveryResult:
    queries: tuple[str, ...]
    candidates: tuple[DiscoveredSource, ...]
    errors: tuple[str, ...]


def discover_case_research(
    case: Mapping[str, object],
    *,
    max_queries: int = MAX_DISCOVERY_QUERIES,
    max_candidates: int = MAX_CANDIDATES,
) -> ResearchDiscoveryResult:
    """Plan and discover sources without changing evidence state."""

    if not 1 <= max_queries <= MAX_DISCOVERY_QUERIES:
        raise ValueError("Invalid research query limit")

    if not 1 <= max_candidates <= MAX_CANDIDATES:
        raise ValueError("Invalid candidate limit")

    planned = plan_research(
        case,
        max_queries=max_queries,
    )

    candidates = []
    errors = []
    seen = set()

    for item in planned:
        if len(candidates) >= max_candidates:
            break

        remaining = max_candidates - len(candidates)

        try:
            results = discover_sources(
                item.query,
                max_results=min(3, remaining),
            )
        except Exception as exc:
            # Discovery failures are reported without promoting
            # incomplete or unreliable sources to evidence.
            errors.append(
                f"{item.purpose}: {type(exc).__name__}"
            )
            continue

        for source in results:
            normalized = source.url.casefold()

            if normalized in seen:
                continue

            if source.verification_status != "unverified":
                continue

            seen.add(normalized)
            candidates.append(source)

            if len(candidates) >= max_candidates:
                break

    return ResearchDiscoveryResult(
        queries=tuple(item.query for item in planned),
        candidates=tuple(candidates),
        errors=tuple(errors),
    )
