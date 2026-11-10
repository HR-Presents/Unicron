import pytest

from app.research_planner import (
    MAX_QUERIES,
    MAX_QUERY_LENGTH,
    plan_research,
)


CASE = {
    "title": "AI-Assisted Public Healthcare Resource Allocation",
    "summary": "Assess governance, fairness and resource allocation.",
    "domain": "Healthcare",
}


def test_generates_six_distinct_queries():
    queries = plan_research(CASE)

    assert len(queries) == MAX_QUERIES
    assert len({q.query.casefold() for q in queries}) == MAX_QUERIES
    assert all(q.purpose and q.jurisdiction for q in queries)


def test_empty_case_produces_no_queries():
    assert plan_research({}) == []
    assert plan_research({
        "title": "",
        "summary": "",
        "domain": "",
    }) == []


def test_query_count_can_be_restricted():
    queries = plan_research(CASE, max_queries=2)

    assert len(queries) == 2


@pytest.mark.parametrize("limit", [0, -1, 7, 100])
def test_invalid_query_limits_are_rejected(limit):
    with pytest.raises(ValueError):
        plan_research(CASE, max_queries=limit)


def test_long_input_respects_query_length_limit():
    queries = plan_research({
        "title": "healthcare " * 200,
        "summary": "governance " * 200,
        "domain": "public policy " * 100,
    })

    assert queries
    assert all(len(q.query) <= MAX_QUERY_LENGTH for q in queries)


def test_duplicate_terms_are_removed_from_subject():
    queries = plan_research({
        "title": "healthcare healthcare healthcare",
        "summary": "healthcare governance governance",
        "domain": "healthcare",
    })

    assert queries
    assert queries[0].query.startswith(
        "healthcare governance "
    )


def test_planning_is_deterministic():
    assert plan_research(CASE) == plan_research(CASE)
