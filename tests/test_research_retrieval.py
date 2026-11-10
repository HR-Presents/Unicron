import socket
from unittest.mock import patch

import pytest

from app.research_retrieval import (
    RetrievalError,
    retrieve_document,
    validate_public_https_url,
)


def fake_dns(ip):
    return [
        (
            socket.AF_INET6 if ":" in ip else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (ip, 443),
        )
    ]


@pytest.mark.parametrize("url", [
    "http://example.com/policy",
    "https://127.0.0.1/policy",
    "https://user:pass@example.com/policy",
    "https://example.com:8080/policy",
    "https://example.com./policy",
    "https://example.com%00.attacker.test/policy",
    "file:///etc/passwd",
])
def test_invalid_urls_rejected(url):
    with pytest.raises(RetrievalError):
        validate_public_https_url(url)


@pytest.mark.parametrize("ip", [
    "127.0.0.1",
    "10.0.0.1",
    "172.16.0.1",
    "192.168.1.1",
    "169.254.169.254",
    "0.0.0.0",
    "::1",
    "fc00::1",
    "fe80::1",
])
def test_non_global_dns_addresses_rejected(ip):
    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        return_value=fake_dns(ip),
    ):
        with pytest.raises(RetrievalError):
            validate_public_https_url(
                "https://policy.example/document"
            )


def test_public_dns_address_accepted():
    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        return_value=fake_dns("8.8.8.8"),
    ):
        assert validate_public_https_url(
            "https://policy.example/document"
        ) == "https://policy.example/document"


def test_mixed_public_and_private_dns_rejected():
    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        return_value=(
            fake_dns("8.8.8.8")
            + fake_dns("127.0.0.1")
        ),
    ):
        with pytest.raises(RetrievalError):
            validate_public_https_url(
                "https://policy.example/document"
            )


def test_dns_resolution_failure_rejected():
    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        side_effect=socket.gaierror("DNS failed"),
    ):
        with pytest.raises(RetrievalError):
            validate_public_https_url(
                "https://policy.example/document"
            )


def test_live_retrieval_remains_disabled():
    with patch(
        "app.research_retrieval.socket.getaddrinfo",
        return_value=fake_dns("8.8.8.8"),
    ):
        with pytest.raises(
            RetrievalError,
            match="DNS-rebinding protection",
        ):
            retrieve_document(
                "https://policy.example/document"
            )
