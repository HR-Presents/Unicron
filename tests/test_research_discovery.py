import io
import json
from unittest.mock import Mock, patch

import pytest

from app.research_discovery import (
    DiscoveryError,
    discover_sources,
)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.buffer = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.buffer.read(size)


def test_valid_results_are_unverified():
    payload = {
        "web": {
            "results": [
                {
                    "title": "Government guidance",
                    "url": "https://example.gov/policy",
                    "description": "Official policy information",
                }
            ]
        }
    }

    with patch(
        "app.research_discovery.urllib.request.build_opener",
        return_value=Mock(open=Mock(return_value=FakeResponse(payload))),
    ):
        results = discover_sources(
            "UAE healthcare policy",
            api_key="test-key",
        )

    assert len(results) == 1
    assert results[0].verification_status == "unverified"
    assert results[0].url == "https://example.gov/policy"


def test_unsafe_and_duplicate_urls_are_filtered():
    payload = {
        "web": {
            "results": [
                {"url": "http://example.com"},
                {"url": "https://user:pass@example.com"},
                {"url": "https://example.com:8080"},
                {"url": "https://example.com/valid"},
                {"url": "https://example.com/valid"},
            ]
        }
    }

    with patch(
        "app.research_discovery.urllib.request.build_opener",
        return_value=Mock(open=Mock(return_value=FakeResponse(payload))),
    ):
        results = discover_sources(
            "healthcare governance",
            api_key="test-key",
        )

    assert len(results) == 1
    assert results[0].url == "https://example.com/valid"


@pytest.mark.parametrize("query", ["", " ", "a" * 181])
def test_invalid_queries_are_rejected(query):
    with pytest.raises(ValueError):
        discover_sources(query, api_key="test-key")


@pytest.mark.parametrize("count", [0, 11])
def test_invalid_result_limits_are_rejected(count):
    with pytest.raises(ValueError):
        discover_sources(
            "UAE healthcare",
            api_key="test-key",
            max_results=count,
        )


def test_missing_api_key_uses_keyless_fallback():
    with patch(
        "app.research_discovery._discover_keyless_sources",
        return_value=[],
    ) as fallback:
        results = discover_sources(
            "UAE healthcare",
            api_key="",
        )

    assert results == []
    fallback.assert_called_once_with(
        "UAE healthcare",
        max_results=5,
    )


def test_invalid_provider_response_fails_closed():
    with patch(
        "app.research_discovery.urllib.request.build_opener",
        return_value=Mock(open=Mock(return_value=FakeResponse({"unexpected": []}))),
    ):
        with pytest.raises(DiscoveryError):
            discover_sources(
                "UAE healthcare",
                api_key="test-key",
            )


def test_search_provider_redirects_are_rejected():
    import urllib.error
    import urllib.request
    from app.research_discovery import SEARCH_ENDPOINT

    captured = {}

    def fake_open(opener, request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout

        handler = next(
            h for h in opener.handlers
            if isinstance(h, urllib.request.HTTPRedirectHandler)
        )

        redirect = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": "https://unexpected.example/"},
            "https://unexpected.example/",
        )

        assert redirect is None

        raise urllib.error.HTTPError(
            request.full_url,
            302,
            "Found",
            {"Location": "https://unexpected.example/"},
            None,
        )

    with patch(
        "app.research_discovery.urllib.request.OpenerDirector.open",
        autospec=True,
        side_effect=fake_open,
    ):
        with pytest.raises(DiscoveryError):
            discover_sources(
                "UAE healthcare policy",
                api_key="test-key",
            )

    assert captured["url"].startswith(SEARCH_ENDPOINT)
    assert captured["timeout"] == 12
