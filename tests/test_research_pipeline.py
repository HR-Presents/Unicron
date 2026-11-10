"""Tests for bounded, unverified research discovery."""

from unittest.mock import patch

import pytest

from app.research_discovery import DiscoveredSource
from app.research_pipeline import discover_case_research


CASE = {
    "title": "AI-Assisted Public Healthcare Resource Allocation",
    "summary": "Evaluate UAE healthcare governance and policy",
    "domain": "healthcare",
}


def source(url, status="unverified"):
    return DiscoveredSource(
        title="Research document",
        url=url,
        description="Policy research",
        query="healthcare policy",
        verification_status=status,
    )


def test_discovery_returns_unverified_candidates():
    with patch(
        "app.research_pipeline.discover_sources",
        return_value=[source("https://example.org/policy")],
    ):
        result = discover_case_research(CASE)

    assert result.candidates
    assert all(
        item.verification_status == "unverified"
        for item in result.candidates
    )
    assert len(result.queries) <= 3


def test_duplicate_urls_are_removed():
    with patch(
        "app.research_pipeline.discover_sources",
        return_value=[
            source("https://example.org/policy"),
            source("https://example.org/policy"),
        ],
    ):
        result = discover_case_research(CASE)

    assert len(result.candidates) == 1


def test_verified_results_are_not_promoted():
    with patch(
        "app.research_pipeline.discover_sources",
        return_value=[
            source("https://example.org/verified", "verified"),
            source("https://example.org/unverified"),
        ],
    ):
        result = discover_case_research(CASE)

    assert len(result.candidates) == 1
    assert result.candidates[0].url.endswith("/unverified")


def test_discovery_failure_is_reported():
    with patch(
        "app.research_pipeline.discover_sources",
        side_effect=RuntimeError("Provider unavailable"),
    ):
        result = discover_case_research(CASE)

    assert not result.candidates
    assert result.errors
    assert all("RuntimeError" in error for error in result.errors)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_queries": 0},
        {"max_queries": 4},
        {"max_candidates": 0},
        {"max_candidates": 10},
    ],
)
def test_invalid_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        discover_case_research(CASE, **kwargs)


def test_candidate_limit_is_enforced():
    with patch(
        "app.research_pipeline.discover_sources",
        return_value=[
            source(f"https://example.org/{i}")
            for i in range(10)
        ],
    ):
        result = discover_case_research(
            CASE,
            max_candidates=2,
        )

    assert len(result.candidates) == 2
