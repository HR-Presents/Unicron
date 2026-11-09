"""Security regression tests for investigation source selection."""

from app.investigation import filter_sources


def source(
    *,
    status="verified",
    source_type="policy",
    authority="Official Authority",
    jurisdiction="UAE",
    official_url="https://example.gov/policy",
    source_note="policy benchmark",
):
    return {
        "verification_status": status,
        "source_type": source_type,
        "authority": authority,
        "jurisdiction": jurisdiction,
        "official_url": official_url,
        "source_note": source_note,
        "content": "Example policy evidence",
    }


def test_verified_policy_is_accepted():
    item = source()
    assert filter_sources([item], "policy") == [item]


def test_verified_benchmark_is_accepted():
    item = source(source_type="benchmark")
    assert filter_sources([item], "benchmark") == [item]


def test_unverified_policy_is_rejected():
    assert filter_sources(
        [source(status="unverified")], "policy"
    ) == []


def test_rejected_policy_is_rejected():
    assert filter_sources(
        [source(status="rejected")], "policy"
    ) == []


def test_missing_provenance_is_rejected():
    item = source()
    item.pop("verification_status")
    assert filter_sources([item], "policy") == []


def test_source_note_cannot_bypass_verification():
    item = source(
        status="unverified",
        source_note="official verified policy benchmark",
    )
    assert filter_sources([item], "policy") == []


def test_missing_authority_is_rejected():
    assert filter_sources(
        [source(authority=" ")], "policy"
    ) == []


def test_missing_jurisdiction_is_rejected():
    assert filter_sources(
        [source(jurisdiction="")], "policy"
    ) == []


def test_missing_official_url_is_rejected():
    assert filter_sources(
        [source(official_url=" ")], "policy"
    ) == []


def test_wrong_source_type_is_rejected():
    assert filter_sources(
        [source(source_type="benchmark")], "policy"
    ) == []


def test_unsupported_source_type_is_rejected():
    assert filter_sources(
        [source(source_type="other")], "policy"
    ) == []


def test_unknown_filter_kind_is_rejected():
    assert filter_sources(
        [source()], "unknown"
    ) == []


def test_mixed_sources_only_return_verified_matches():
    valid = source()
    unverified = source(status="unverified")
    rejected = source(status="rejected")
    wrong_type = source(source_type="benchmark")

    assert filter_sources(
        [unverified, valid, rejected, wrong_type],
        "policy",
    ) == [valid]
