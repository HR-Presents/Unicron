"""Bounded HTTPS document retrieval for research candidates.

This module returns untrusted document bytes. It does not
authenticate sources or write to the evidence database.
"""
from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_URL_LENGTH = 2000
TIMEOUT_SECONDS = 12

ALLOWED_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/pdf",
}


class RetrievalError(RuntimeError):
    """Document retrieval failed a security or availability check."""


@dataclass(frozen=True)
class RetrievedDocument:
    url: str
    content_type: str
    payload: bytes
    verification_status: str = "unverified"


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _validate_https_url_syntax(url: str) -> urllib.parse.SplitResult:
    """Validate URL structure without performing network access."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL_LENGTH:
        raise RetrievalError("Invalid document URL")

    if any(ord(c) <= 32 or ord(c) == 127 for c in url) or chr(92) in url:
        raise RetrievalError("Unsafe document URL characters")

    try:
        parsed = urllib.parse.urlsplit(url)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise RetrievalError("Only public HTTPS URLs are allowed")

        hostname = parsed.hostname

        if hostname.endswith(".") or "%" in hostname:
            raise RetrievalError("Ambiguous hostname rejected")

        try:
            hostname.encode("ascii")
        except UnicodeEncodeError as exc:
            raise RetrievalError("Non-ASCII hostname rejected") from exc

        if not all(c.isalnum() or c in ".-:" for c in hostname):
            raise RetrievalError("Malformed hostname rejected")

        return parsed

    except ValueError as exc:
        raise RetrievalError("Document URL validation failed") from exc


def _resolve_public_addresses(hostname: str) -> list[str]:
    """Resolve and reject any unsafe DNS destination."""
    try:
        addresses = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise RetrievalError("Document DNS lookup failed") from exc

    if not addresses:
        raise RetrievalError("Hostname did not resolve")

    public_ips = []

    for entry in addresses:
        try:
            address = ipaddress.ip_address(entry[4][0])
        except ValueError as exc:
            raise RetrievalError("Invalid resolved address") from exc

        if (
            not address.is_global
            or address.is_multicast
            or address.is_unspecified
        ):
            raise RetrievalError(
                "Private or non-global network address rejected"
            )

        public_ips.append(str(address))

    return public_ips


def validate_public_https_url(url: str) -> str:
    """Validate URL syntax and all resolved destinations."""
    parsed = _validate_https_url_syntax(url)
    assert parsed.hostname is not None
    _resolve_public_addresses(parsed.hostname)
    return url


def retrieve_document(url: str) -> RetrievedDocument:
    """Fetch bounded untrusted bytes from a public HTTPS URL.

    DNS validation is preliminary. Production use also requires
    pinning the validated destination IP at connection time to
    eliminate DNS rebinding between validation and connection.
    """
    validate_public_https_url(url)

    # Deliberately disabled until connection-time IP pinning
    # and network-boundary protections are implemented.
    raise RetrievalError(
        "Live retrieval disabled pending DNS-rebinding protection"
    )


def _download_https_document(url: str) -> RetrievedDocument:
    """Download via a pinned public IP with TLS hostname verification.

    Internal transport: not enabled through retrieve_document yet.
    """
    import http.client
    import ssl
    import time

    deadline = time.monotonic() + TIMEOUT_SECONDS
    parsed = _validate_https_url_syntax(url)
    validated_url = url
    hostname = parsed.hostname
    assert hostname is not None

    # Resolve once, validate every answer, and pin the selected IP.
    public_ips = _resolve_public_addresses(hostname)

    selected_ip = public_ips[0]
    tls_context = ssl.create_default_context()
    tls_context.check_hostname = True
    tls_context.verify_mode = ssl.CERT_REQUIRED

    class PinnedHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RetrievalError(
                    "Document download deadline exceeded"
                )

            raw_socket = socket.create_connection(
                (selected_ip, 443),
                timeout=min(TIMEOUT_SECONDS, remaining),
            )

            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RetrievalError(
                        "Document download deadline exceeded"
                    )

                raw_socket.settimeout(
                    min(TIMEOUT_SECONDS, remaining)
                )

                self.sock = tls_context.wrap_socket(
                    raw_socket,
                    server_hostname=hostname,
                )
            except BaseException:
                raw_socket.close()
                raise

    path = urllib.parse.urlunsplit((
        "",
        "",
        parsed.path or "/",
        parsed.query,
        "",
    ))

    connection = PinnedHTTPSConnection(
        hostname,
        port=443,
        timeout=TIMEOUT_SECONDS,
        context=tls_context,
    )

    try:
        connection.request(
            "GET",
            path,
            headers={
                "Accept": (
                    "application/pdf, text/plain, "
                    "text/markdown, text/csv"
                ),
                "Accept-Encoding": "identity",
                "User-Agent": "UNICRON-Research/1.0",
                "Connection": "close",
            },
        )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RetrievalError(
                "Document download deadline exceeded"
            )

        if connection.sock is not None:
            connection.sock.settimeout(
                min(TIMEOUT_SECONDS, remaining)
            )

        response = connection.getresponse()

        # Reject redirects and all other non-success statuses.
        if response.status != 200:
            raise RetrievalError(
                f"Document server returned HTTP {response.status}"
            )

        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise RetrievalError("Compressed documents are not supported")

        content_type = (
            response.getheader("Content-Type", "")
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        if content_type not in ALLOWED_TYPES:
            raise RetrievalError("Unsupported document content type")

        length_header = response.getheader("Content-Length")

        if length_header is not None:
            try:
                declared_length = int(length_header)
            except ValueError as exc:
                raise RetrievalError(
                    "Invalid document content length"
                ) from exc

            if not 0 <= declared_length <= MAX_DOCUMENT_BYTES:
                raise RetrievalError(
                    "Document exceeds permitted size"
                )

        chunks = []
        total = 0

        while True:
            time_remaining = deadline - time.monotonic()

            if time_remaining <= 0:
                raise RetrievalError("Document download deadline exceeded")

            if connection.sock is not None:
                connection.sock.settimeout(
                    min(TIMEOUT_SECONDS, time_remaining)
                )

            remaining = MAX_DOCUMENT_BYTES - total + 1
            chunk = response.read(min(65536, remaining))

            if not chunk:
                break

            total += len(chunk)

            if total > MAX_DOCUMENT_BYTES:
                raise RetrievalError(
                    "Document exceeds permitted size"
                )

            chunks.append(chunk)

        payload = b"".join(chunks)

        if not payload:
            raise RetrievalError("Document is empty")

        return RetrievedDocument(
            url=validated_url,
            content_type=content_type,
            payload=payload,
        )

    except RetrievalError:
        raise
    except (
        OSError,
        TimeoutError,
        ssl.SSLError,
        http.client.HTTPException,
    ) as exc:
        raise RetrievalError(
            "Secure document download failed"
        ) from exc
    finally:
        connection.close()
