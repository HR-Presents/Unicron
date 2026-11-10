
import pytest

from backend.app.evidence import sentence_source_citations


DOC = "verified-document"


def make_passages(text, chunk_size=180, overlap=100):
    """Create consecutive overlapping chunks from one source."""
    assert chunk_size > overlap >= 80

    rows = []
    step = chunk_size - overlap

    for index, start in enumerate(range(0, len(text), step)):
        content = text[start:start + chunk_size]

        if not content:
            break

        rows.append({
            "document_id": DOC,
            "position": 10 + index,
            "content": content,
        })

        if start + chunk_size >= len(text):
            break

    return rows


def test_sentence_spanning_chunks_has_both_citations():
    sentence = (
        "The oversight requirement begins here and continues "
        "with a verified conclusion describing the responsible "
        "human review process and documented accountability."
    )

    text = "A" * 110 + sentence + "B" * 110
    rows = make_passages(text)

    assert all(sentence not in row["content"] for row in rows)

    assert sentence_source_citations(
        rows, sentence
    ) == [f"{DOC}#p11", f"{DOC}#p12"]



def test_sentence_fully_inside_one_chunk():
    sentence = "A verified oversight requirement applies."

    rows = [{
        "document_id": DOC,
        "position": 10,
        "content": "X" * 100 + sentence + "Y" * 100,
    }]

    assert sentence_source_citations(
        rows, sentence
    ) == [f"{DOC}#p10"]


def test_rejects_text_not_in_source():
    rows = make_passages("A" * 350)

    with pytest.raises(ValueError):
        sentence_source_citations(
            rows,
            "This sentence was never in the source.",
        )


def test_rejects_ambiguous_repeated_sentence():
    sentence = "A repeated verified sentence."

    rows = [{
        "document_id": DOC,
        "position": 10,
        "content": sentence + " " + sentence,
    }]

    with pytest.raises(ValueError):
        sentence_source_citations(rows, sentence)



def test_rejects_duplicate_passage_positions():
    sentence = "A verified requirement is documented."
    rows = [
        {
            "document_id": DOC,
            "position": 10,
            "content": "X" * 100 + sentence,
        },
        {
            "document_id": DOC,
            "position": 10,
            "content": sentence + "Y" * 100,
        },
    ]

    with pytest.raises(ValueError):
        sentence_source_citations(rows, sentence)


def test_rejects_reordered_passages():
    sentence = "A verified requirement is documented."
    rows = [
        {
            "document_id": DOC,
            "position": 11,
            "content": "X" * 100 + sentence,
        },
        {
            "document_id": DOC,
            "position": 10,
            "content": sentence + "Y" * 100,
        },
    ]

    with pytest.raises(ValueError):
        sentence_source_citations(rows, sentence)


def test_rejects_nonconsecutive_passages():
    sentence = "A verified requirement is documented."
    rows = [
        {
            "document_id": DOC,
            "position": 10,
            "content": "X" * 100 + sentence,
        },
        {
            "document_id": DOC,
            "position": 12,
            "content": sentence + "Y" * 100,
        },
    ]

    with pytest.raises(ValueError):
        sentence_source_citations(rows, sentence)


def test_rejects_more_than_four_citations():
    sentence = (
        "This verified regulatory requirement describes "
        "a continuous and carefully documented oversight "
        "procedure extending across multiple evidence chunks. "
    ) * 5

    rows = make_passages(
        "X" * 110 + sentence + "Y" * 110,
        chunk_size=180,
        overlap=100,
    )

    with pytest.raises(ValueError):
        sentence_source_citations(
            rows,
            sentence,
            max_citations=4,
        )


def test_reconstructed_excerpt_preserves_exact_citations():
    from backend.app.evidence import build_reconstructed_excerpt

    sentence = (
        "The oversight requirement begins here and continues "
        "with a verified conclusion describing the responsible "
        "human review process and documented accountability."
    )

    rows = make_passages("A" * 110 + sentence + "B" * 110)

    result = build_reconstructed_excerpt(
        rows,
        sentence,
        filename="verified_policy.txt",
    )

    assert result["text"] == sentence
    assert result["citations"] == [
        f"{DOC}#p11",
        f"{DOC}#p12",
    ]
    assert result["filename"] == "verified_policy.txt"



def test_reconstructed_excerpt_rejects_unverified_join():
    from backend.app.evidence import build_reconstructed_excerpt

    rows = [
        {
            "document_id": DOC,
            "position": 10,
            "content": "A verified policy sentence ends here.",
        },
        {
            "document_id": DOC,
            "position": 11,
            "content": "An unrelated document fragment begins here.",
        },
    ]

    with pytest.raises(ValueError):
        build_reconstructed_excerpt(
            rows,
            "A verified policy sentence ends here.",
            filename="verified_policy.txt",
        )


def test_reconstructed_excerpt_rejects_missing_sentence():
    from backend.app.evidence import build_reconstructed_excerpt

    rows = make_passages(
        "A" * 110
        + "The verified source describes oversight requirements."
        + "B" * 110
    )

    with pytest.raises(ValueError):
        build_reconstructed_excerpt(
            rows,
            "This requirement was invented by the model.",
            filename="verified_policy.txt",
        )



def test_extract_complete_reconstructed_sentences_skips_initial_fragment():
    from backend.app.evidence import extract_complete_reconstructed_sentences

    fragment = (
        "ural persons to whom oversight is assigned are enabled "
        "to monitor the operation of high-risk AI systems."
    )

    complete = (
        "The requirement for separate verification by two natural "
        "persons shall not apply where Union or national law "
        "considers the requirement disproportionate."
    )

    text = fragment + " " + complete

    rows = make_passages(text, chunk_size=180, overlap=100)

    excerpts = extract_complete_reconstructed_sentences(
        rows,
        filename="verified_policy.txt",
        max_chars=420,
        max_citations=4,
    )

    assert any(item["text"] == complete for item in excerpts)
    assert all(fragment not in item["text"] for item in excerpts)

    for item in excerpts:
        assert item["citations"]
        assert len(item["citations"]) <= 4
        assert len(item["text"]) <= 420
        assert item["filename"] == "verified_policy.txt"



def test_extract_complete_reconstructed_sentences_rejects_long_sentence():
    from backend.app.evidence import extract_complete_reconstructed_sentences

    words = [
        f"requirement{i:03d}" for i in range(100)
    ]
    long_sentence = (
        "The regulator requires "
        + " ".join(words)
        + "."
    )

    text = "Initial incomplete fragment. " + long_sentence

    rows = make_passages(
        text,
        chunk_size=180,
        overlap=100,
    )

    excerpts = extract_complete_reconstructed_sentences(
        rows,
        filename="verified_policy.txt",
        max_chars=420,
    )

    assert all(
        item["text"] != long_sentence
        for item in excerpts
    )


def test_preserves_complete_opening_legal_paragraph():
    from backend.app.evidence import extract_complete_reconstructed_sentences

    sentence = (
        "Article 10\n"
        "Data and data governance\n"
        "1. High-risk AI systems shall use appropriate "
        "training and testing datasets."
    )

    rows = make_passages(
        "A" * 110 + sentence + "B" * 110
    )

    # This fixture begins mid-source, so the initial
    # incomplete fragment must not become an excerpt.
    excerpts = extract_complete_reconstructed_sentences(
        rows,
        filename="verified_policy.txt",
        max_chars=420,
    )

    assert all(item["text"] != sentence for item in excerpts)


def test_preserves_complete_first_sentence_when_source_starts_at_boundary():
    from backend.app.evidence import extract_complete_reconstructed_sentences

    first = (
        "Article 10\n"
        "Data and data governance\n"
        "1. High-risk AI systems shall use appropriate "
        "training and testing datasets."
    )

    second = (
        "2. Training datasets shall undergo appropriate "
        "quality assessment before deployment."
    )

    rows = make_passages(first + "\n" + second)

    excerpts = extract_complete_reconstructed_sentences(
        rows,
        filename="verified_policy.txt",
        max_chars=420,
    )

    assert any(
        "1. High-risk AI systems" in item["text"]
        for item in excerpts
    )
