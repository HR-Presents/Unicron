"""Conservative reconstruction of consecutive evidence passages.

A reconstruction is valid only when source document identity,
passage order and literal text overlap can be verified.
"""

def reconstruct_adjacent_passages(rows, max_chars=1800, min_overlap=80):
    """Return verified reconstructed text and contributing citations.

    Rows must contain document_id, position and content.
    Invalid adjacency ends the current reconstruction.
    """
    if max_chars < 1 or min_overlap < 1:
        raise ValueError("Limits must be positive")

    passages = sorted(
        (dict(row) for row in rows),
        key=lambda row: (row["document_id"], row["position"]),
    )
    from collections import Counter

    position_counts = Counter(
        (row["document_id"], row["position"])
        for row in passages
    )
    ambiguous_positions = {
        key for key, count in position_counts.items()
        if count > 1
    }

    results = []
    current = None

    for passage in passages:
        document_id = passage["document_id"]
        position = passage["position"]
        content = passage["content"]

        if (
            (document_id, position) in ambiguous_positions
            or not isinstance(content, str)
            or not content.strip()
            or len(content) > max_chars
        ):
            current = None
            continue

        citation = f"{document_id}#p{position}"

        if current is not None:
            consecutive = (
                current["document_id"] == document_id
                and current["last_position"] + 1 == position
            )

            overlap = 0
            if consecutive:
                maximum = min(
                    len(current["last_content"]),
                    len(content),
                )
                for size in range(maximum, min_overlap - 1, -1):
                    if current["last_content"].endswith(content[:size]):
                        overlap = size
                        break

            if overlap:
                combined = current["text"] + content[overlap:]
                if len(combined) <= max_chars:
                    current["text"] = combined
                    current["citations"].append(citation)
                    current["last_position"] = position
                    current["last_content"] = content
                    continue

        current = {
            "document_id": document_id,
            "last_position": position,
            "last_content": content,
            "text": content,
            "citations": [citation],
        }
        results.append(current)

    return [
        {
            "document_id": result["document_id"],
            "text": result["text"],
            "citations": result["citations"],
        }
        for result in results
    ]



def build_reconstructed_excerpt(anchor, passages, max_chars=1800):
    """Reconstruct evidence around an anchor without losing provenance.

    Returns None when the anchor cannot be represented safely.
    Every contributing passage retains its original citation ID.
    """
    document_id = anchor["document_id"]
    position = anchor["position"]

    nearby = [
        row for row in passages
        if row["document_id"] == document_id
        and position - 1 <= row["position"] <= position + 1
    ]

    reconstructed = reconstruct_adjacent_passages(
        nearby, max_chars=max_chars
    )

    anchor_citation = f"{document_id}#p{position}"

    for item in reconstructed:
        if anchor_citation in item["citations"]:
            return {
                "citation": anchor_citation,
                "citations": item["citations"],
                "text": item["text"],
            }

    return None



def prepare_evidence_excerpt(anchor, passages, max_chars=1800):
    """Prepare an excerpt with explicit contributing passage citations.

    Returns None if reconstruction cannot safely include the anchor.
    """
    reconstructed = build_reconstructed_excerpt(
        anchor, passages, max_chars=max_chars
    )

    if reconstructed is None:
        return None

    source_by_citation = {}
    duplicate_citations = set()

    for row in passages:
        if row["document_id"] != anchor["document_id"]:
            continue

        citation = f"{row['document_id']}#p{row['position']}"
        if citation in source_by_citation:
            duplicate_citations.add(citation)
        else:
            source_by_citation[citation] = row["content"]

    if any(
        citation in duplicate_citations
        for citation in reconstructed["citations"]
    ):
        return None

    if any(
        citation not in source_by_citation
        for citation in reconstructed["citations"]
    ):
        return None

    return {
        "citation": reconstructed["citation"],
        "citations": reconstructed["citations"],
        "filename": anchor["filename"],
        "text": reconstructed["text"],
        "source_passages": [
            {
                "citation": citation,
                "text": source_by_citation[citation],
            }
            for citation in reconstructed["citations"]
        ],
    }
