"""Adversarial URL validation and SSRF regression tests."""

import socket
from unittest.mock import patch

import pytest

from app.research_retrieval import (
    RetrievalError,
    validate_public_https_url,
)


MALICIOUS_URLS = [
    "https://example.com/\r\nX-Injected: yes",
    "https://example.com/\nHost: attacker.test",
    "https://example.com/\tsecret",
    "https://example.com/a b",
    "https://example.com\\@127.0.0.1/",
    "https://example.com/path\\other",
    "https://example.com/\x00",
    "https://example.com/\x7f",
    "https://example.com:444/",
    "https://user@example.com/document",
    "https://example.com./document",
    "https://example.com%00.attacker.test/document",
    "https://☃.example/document",
    "https://example.com/path\nanother",
    "https://example.com/path\ranother",
]


@pytest.mark.parametrize("url", MALICIOUS_URLS)
def test_malicious_urls_rejected_before_network_access(url):
    with patch(
        "app.research_retrieval.socket.getaddrinfo"
    ) as dns:
        with pytest.raises(RetrievalError):
            validate_public_https_url(url)

        dns.assert_not_called()


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
        "100.64.0.1",
        "224.0.0.1",
    ],
)
def test_non_public_dns_addresses_blocked(ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET

    dns_result = [
        (
            family,
            socket.SOCK_STREAM,
            6,
            "",
            (ip, 443),
        )
    ]

    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        return_value=dns_result,
    ):
        with pytest.raises(RetrievalError):
            validate_public_https_url(
                "https://policy.example/document"
            )


def test_mixed_public_private_dns_answers_blocked():
    dns_results = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("8.8.8.8", 443),
        ),
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("127.0.0.1", 443),
        ),
    ]

    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        return_value=dns_results,
    ):
        with pytest.raises(RetrievalError):
            validate_public_https_url(
                "https://policy.example/document"
            )
