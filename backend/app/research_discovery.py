"""External source discovery with explicit unverified status.

Uses a fixed HTTPS search endpoint. Search results are candidates,
not evidence, verified law, or approved policy conclusions.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
MAX_RESULTS = 10
MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True)
class DiscoveredSource:
    title: str
    url: str
    description: str
    query: str
    verification_status: str = "unverified"


class DiscoveryError(RuntimeError):
    """A source discovery request could not be completed."""


def _valid_url(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 2000:
        return False

    try:
        parsed = urllib.parse.urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        return False


def _discover_brave_sources(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
) -> list[DiscoveredSource]:
    """Discover candidate URLs; never mark them verified."""
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 180:
        raise ValueError("Search query must contain 1–180 characters")

    if not 1 <= max_results <= MAX_RESULTS:
        raise ValueError("max_results must be between 1 and 10")

    key = api_key if api_key is not None else os.getenv(
        "BRAVE_SEARCH_API_KEY", ""
    )

    if not key or not key.strip():
        raise DiscoveryError(
            "Brave Search API key is not configured"
        )

    parameters = urllib.parse.urlencode({
        "q": query.strip(),
        "count": max_results,
    })

    request = urllib.request.Request(
        SEARCH_ENDPOINT + "?" + parameters,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": key.strip(),
            "User-Agent": "UNICRON-Research/1.0",
        },
        method="GET",
    )

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(
        NoRedirectHandler()
    )

    try:
        with opener.open(request, timeout=12) as response:
            if response.status != 200:
                raise DiscoveryError("Search provider returned an error")

            payload = response.read(MAX_RESPONSE_BYTES + 1)

            if len(payload) > MAX_RESPONSE_BYTES:
                raise DiscoveryError("Search response exceeded size limit")

    except (urllib.error.URLError, TimeoutError) as exc:
        raise DiscoveryError(
            "Search provider request failed"
        ) from exc

    try:
        data = json.loads(payload)
        entries = data["web"]["results"]
        if not isinstance(entries, list):
            raise ValueError("Invalid results")
    except (ValueError, KeyError, TypeError) as exc:
        raise DiscoveryError(
            "Search provider returned an invalid response"
        ) from exc

    sources = []
    seen = set()

    for item in entries:
        if not isinstance(item, dict):
            continue

        url = item.get("url")

        if not _valid_url(url) or url in seen:
            continue

        seen.add(url)

        sources.append(
            DiscoveredSource(
                title=str(item.get("title") or "")[:300],
                url=url,
                description=str(
                    item.get("description") or ""
                )[:1200],
                query=query.strip(),
            )
        )

        if len(sources) >= max_results:
            break

    return sources



def _official_relevance(url: str, query: str) -> bool:
    """Allowlisted publisher, not a guarantee of topical relevance."""
    from urllib.parse import urlsplit

    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False

    domains = (
        "who.int", "itu.int", "unesco.org", "oecd.org",
        "un.org", "worldbank.org", "u.ae", "gov.ae",
        "mohap.gov.ae", "dha.gov.ae", "doh.gov.ae",
        "ai.gov.ae", "europa.eu", "nist.gov",
        "gov.uk", "health.gov.au",
    )

    return any(
        host == domain or host.endswith("." + domain)
        for domain in domains
    )


def _discover_keyless_sources(
    query: str,
    *,
    max_results: int = 5,
) -> list[DiscoveredSource]:
    """Best-effort public RSS search; never authenticates sources."""
    import xml.etree.ElementTree as ET

    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 180:
        raise ValueError("Search query must contain 1–180 characters")
    if not 1 <= max_results <= MAX_RESULTS:
        raise ValueError("Invalid result limit")

    endpoint = "https://www.bing.com/search?format=rss&" + (
        urllib.parse.urlencode({"q": query.strip()})
    )
    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/rss+xml, application/xml",
            "User-Agent": "UNICRON-Research/1.0",
        },
    )

    class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirectHandler())

    try:
        with opener.open(request, timeout=10) as response:
            if response.status != 200:
                raise DiscoveryError("Public search returned non-200 status")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise DiscoveryError("Public search response too large")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DiscoveryError("Public search request failed") from exc

    try:
        root = ET.fromstring(payload)
        if root.tag != "rss":
            raise ValueError("Not an RSS feed")
    except (ET.ParseError, ValueError) as exc:
        raise DiscoveryError("Public search returned invalid RSS") from exc

    sources = []
    seen = set()

    for item in root.findall("./channel/item"):
        url = (item.findtext("link") or "").strip()

        if not _valid_url(url) or url in seen:
            continue

        if not _official_relevance(url, query):
            continue

        seen.add(url)
        sources.append(
            DiscoveredSource(
                title=(item.findtext("title") or "")[:300],
                url=url,
                description=(item.findtext("description") or "")[:1200],
                query=query.strip(),
            )
        )

        if len(sources) >= max_results:
            break

    return sources


def discover_sources(
    query: str,
    *,
    api_key: str | None = None,
    max_results: int = 5,
) -> list[DiscoveredSource]:
    """Use configured Brave search, otherwise keyless RSS fallback."""
    key = api_key if api_key is not None else os.getenv(
        "BRAVE_SEARCH_API_KEY", ""
    )

    if key and key.strip():
        return _discover_brave_sources(
            query, api_key=key, max_results=max_results
        )

    return _discover_keyless_sources(
        query, max_results=max_results
    )
