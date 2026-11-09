"""Regression tests for conservative adjacent evidence reconstruction."""

from backend.app.adjacent_retrieval import (
    reconstruct_adjacent_passages,
    build_reconstructed_excerpt,
    prepare_evidence_excerpt,
)


def passage(document, position, content):
    return {
        "document_id": document,
        "position": position,
        "content": content,
    }



def test_three_consecutive_passages_reconstruct_without_duplication():
    overlap_a = "verified first overlap " * 5
    overlap_b = "verified second overlap " * 5
    first = "Opening statement. " + overlap_a
    second = overlap_a + "Middle statement. " + overlap_b
    third = overlap_b + "Closing statement."

    result = reconstruct_adjacent_passages([
        passage("doc-a", 3, third),
        passage("doc-a", 1, first),
        passage("doc-a", 2, second),
    ])

    assert len(result) == 1
    assert result[0]["text"] == (
        "Opening statement. "
        + overlap_a
        + "Middle statement. "
        + overlap_b
        + "Closing statement."
    )
    assert result[0]["citations"] == [
        "doc-a#p1", "doc-a#p2", "doc-a#p3"
    ]


def test_duplicate_positions_do_not_create_duplicate_citations():
    shared = "verified overlap " * 6
    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, "Opening " + shared),
        passage("doc-a", 1, "Conflicting " + shared),
        passage("doc-a", 2, shared + "Closing."),
    ])

    assert all(
        len(item["citations"]) == len(set(item["citations"]))
        for item in result
    )
    assert not any(
        item["citations"] == ["doc-a#p1", "doc-a#p2"]
        for item in result
    )


def test_nonmatching_overlap_does_not_merge():
    shared = "verified overlap " * 6
    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, "Opening " + shared),
        passage("doc-a", 2, "Different " + shared + "Closing."),
    ])

    assert len(result) == 2

def test_exact_overlap_reconstructs_and_preserves_both_citations():
    shared = "verified overlap " * 6
    first = "The regulation establishes " + shared
    second = shared + "a documented review process."

    result = reconstruct_adjacent_passages([
        passage("doc-a", 2, second),
        passage("doc-a", 1, first),
    ])

    assert len(result) == 1
    assert result[0]["text"] == first + "a documented review process."
    assert result[0]["citations"] == ["doc-a#p1", "doc-a#p2"]


def test_different_documents_never_merge():
    shared = "verified overlap " * 6
    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, "First " + shared),
        passage("doc-b", 2, shared + "Second."),
    ])
    assert len(result) == 2


def test_nonconsecutive_positions_never_merge():
    shared = "verified overlap " * 6
    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, "First " + shared),
        passage("doc-a", 3, shared + "Second."),
    ])
    assert len(result) == 2


def test_insufficient_overlap_never_merges():
    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, "A" * 79),
        passage("doc-a", 2, "A" * 79 + " new content"),
    ])
    assert len(result) == 2


def test_character_limit_prevents_merge():
    shared = "verified overlap " * 6
    first = "First " + shared
    second = shared + "Additional evidence."

    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, first),
        passage("doc-a", 2, second),
    ], max_chars=len(first))

    assert len(result) == 1
    assert result[0]["text"] == first
    assert result[0]["citations"] == ["doc-a#p1"]


def test_oversized_passage_is_rejected_without_truncation():
    content = "The complete evidence sentence must remain intact."
    result = reconstruct_adjacent_passages([
        passage("doc-a", 1, content),
    ], max_chars=20)

    assert result == []



def test_build_excerpt_preserves_contributing_citations():
    shared = "verified overlap " * 6
    first = passage("doc-a", 1, "Opening " + shared)
    second = passage("doc-a", 2, shared + "Closing.")

    result = build_reconstructed_excerpt(first, [first, second])

    assert result["citation"] == "doc-a#p1"
    assert result["citations"] == ["doc-a#p1", "doc-a#p2"]
    assert result["text"] == "Opening " + shared + "Closing."


def test_build_excerpt_returns_none_for_missing_anchor():
    anchor = passage("doc-a", 2, "Missing anchor.")
    rows = [passage("doc-a", 1, "Unrelated source.")]

    assert build_reconstructed_excerpt(anchor, rows) is None


def test_build_excerpt_rejects_ambiguous_anchor():
    first = passage("doc-a", 1, "First version.")
    conflicting = passage("doc-a", 1, "Conflicting version.")

    assert build_reconstructed_excerpt(
        first, [first, conflicting]
    ) is None


def test_build_excerpt_rejects_oversized_anchor():
    anchor = passage("doc-a", 1, "A" * 100)

    assert build_reconstructed_excerpt(
        anchor, [anchor], max_chars=20
    ) is None



def test_prepared_excerpt_preserves_complete_provenance():
    shared = "verified overlap " * 6
    first = {
        **passage("doc-a", 1, "Opening " + shared),
        "filename": "policy.pdf",
    }
    second = passage("doc-a", 2, shared + "Closing.")

    result = prepare_evidence_excerpt(first, [first, second])

    assert result == {
        "citation": "doc-a#p1",
        "citations": ["doc-a#p1", "doc-a#p2"],
        "filename": "policy.pdf",
        "text": "Opening " + shared + "Closing.",
        "source_passages": [
            {
                "citation": "doc-a#p1",
                "text": first["content"],
            },
            {
                "citation": "doc-a#p2",
                "text": second["content"],
            },
        ],
    }


def test_prepared_excerpt_rejects_missing_anchor():
    anchor = {
        **passage("doc-a", 2, "Missing."),
        "filename": "policy.pdf",
    }

    result = prepare_evidence_excerpt(
        anchor,
        [passage("doc-a", 1, "Unrelated.")],
    )

    assert result is None


def test_prepared_excerpt_does_not_cross_document_boundaries():
    shared = "verified overlap " * 6
    anchor = {
        **passage("doc-a", 1, "Opening " + shared),
        "filename": "policy-a.pdf",
    }
    other = passage("doc-b", 2, shared + "Closing.")

    result = prepare_evidence_excerpt(anchor, [anchor, other])

    assert result["citations"] == ["doc-a#p1"]
    assert result["text"] == anchor["content"]



def test_prepared_excerpt_excludes_ambiguous_neighbor():
    shared = "verified overlap " * 6

    anchor = {
        **passage("doc-a", 1, "Opening " + shared),
        "filename": "policy.pdf",
    }
    neighbor = passage("doc-a", 2, shared + "Closing.")
    conflicting = passage("doc-a", 2, shared + "Conflicting.")

    result = prepare_evidence_excerpt(
        anchor, [anchor, neighbor, conflicting]
    )

    assert result is not None
    assert result["citation"] == "doc-a#p1"
    assert result["citations"] == ["doc-a#p1"]
    assert result["text"] == anchor["content"]
    assert result["source_passages"] == [
        {
            "citation": "doc-a#p1",
            "text": anchor["content"],
        }
    ]


def test_prepared_excerpt_rejects_duplicate_anchor():
    anchor = {
        **passage("doc-a", 1, "Original statement."),
        "filename": "policy.pdf",
    }
    conflicting = passage(
        "doc-a", 1, "Conflicting statement."
    )

    assert prepare_evidence_excerpt(
        anchor, [anchor, conflicting]
    ) is None
