import socket
from unittest.mock import patch

import pytest

from app.research_retrieval import (
    MAX_DOCUMENT_BYTES,
    RetrievalError,
    _download_https_document,
)


def public_dns(*args, **kwargs):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("8.8.8.8", 443),
        )
    ]


class FakeResponse:
    def __init__(
        self,
        *,
        status=200,
        content_type="text/plain",
        payload=b"Official policy document",
        content_length=None,
        content_encoding=None,
    ):
        self.status = status
        self.payload = payload
        self.position = 0
        self.headers = {
            "Content-Type": content_type,
        }

        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

        if content_encoding is not None:
            self.headers["Content-Encoding"] = content_encoding

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, size=-1):
        if size < 0:
            size = len(self.payload)

        result = self.payload[
            self.position:self.position + size
        ]

        self.position += len(result)
        return result


class FakeConnection:
    response = None
    requests = []

    def __init__(self, *args, **kwargs):
        self.closed = False

    def request(self, method, path, headers):
        self.requests.append((method, path, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def run_download(response):
    FakeConnection.response = response
    FakeConnection.requests = []

    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            side_effect=public_dns,
        ),
        patch(
            "ssl.create_default_context",
        ),
        patch(
            "http.client.HTTPSConnection.request",
            autospec=True,
        ),
        patch(
            "http.client.HTTPSConnection.getresponse",
            return_value=response,
        ),
        patch(
            "http.client.HTTPSConnection.close",
            autospec=True,
        ),
    ):
        # The transport defines its own HTTPSConnection subclass.
        # Patch the socket connection to avoid external networking.
        with patch(
            "app.research_retrieval.socket.create_connection"
        ):
            return _download_https_document(
                "https://policy.example/document?q=healthcare"
            )


def test_successful_text_document():
    result = run_download(
        FakeResponse(payload=b"Official guidance")
    )

    assert result.payload == b"Official guidance"
    assert result.content_type == "text/plain"
    assert result.verification_status == "unverified"


@pytest.mark.parametrize("status", [301, 302, 307, 404, 500])
def test_non_success_status_rejected(status):
    with pytest.raises(RetrievalError):
        run_download(FakeResponse(status=status))


def test_unsupported_content_type_rejected():
    with pytest.raises(RetrievalError):
        run_download(
            FakeResponse(content_type="text/html")
        )


def test_compressed_response_rejected():
    with pytest.raises(RetrievalError):
        run_download(
            FakeResponse(content_encoding="gzip")
        )


def test_declared_oversized_response_rejected():
    with pytest.raises(RetrievalError):
        run_download(
            FakeResponse(
                content_length=MAX_DOCUMENT_BYTES + 1
            )
        )


def test_streamed_oversized_response_rejected():
    with pytest.raises(RetrievalError):
        run_download(
            FakeResponse(
                payload=b"x" * (MAX_DOCUMENT_BYTES + 1)
            )
        )


def test_invalid_content_length_rejected():
    with pytest.raises(RetrievalError):
        run_download(
            FakeResponse(content_length="invalid")
        )


def test_empty_document_rejected():
    with pytest.raises(RetrievalError):
        run_download(
            FakeResponse(payload=b"")
        )


def test_pinned_socket_and_original_tls_hostname():
    from unittest.mock import Mock
    import ssl

    response = FakeResponse(payload=b"Verified transport test")
    raw_socket = Mock()
    tls_socket = Mock()

    tls_context = Mock()
    tls_context.check_hostname = True
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.wrap_socket.return_value = tls_socket

    connections = []

    def record_connection(address, timeout):
        connections.append((address, timeout))
        return raw_socket

    original_request = __import__(
        "http.client", fromlist=["HTTPSConnection"]
    ).HTTPSConnection.request

    def fake_request(connection, method, path, headers):
        connection.connect()
        assert method == "GET"
        assert path == "/document?q=healthcare"
        assert headers["Accept-Encoding"] == "identity"

    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            side_effect=public_dns,
        ),
        patch(
            "socket.create_connection",
            side_effect=record_connection,
        ),
        patch(
            "ssl.create_default_context",
            return_value=tls_context,
        ),
        patch(
            "http.client.HTTPSConnection.request",
            fake_request,
        ),
        patch(
            "http.client.HTTPSConnection.getresponse",
            return_value=response,
        ),
        patch(
            "http.client.HTTPSConnection.close",
            autospec=True,
        ),
    ):
        result = _download_https_document(
            "https://policy.example/document?q=healthcare"
        )

    assert result.payload == b"Verified transport test"
    assert len(connections) == 1
    assert connections[0][0] == ("8.8.8.8", 443)
    assert 0 < connections[0][1] <= 12
    tls_context.wrap_socket.assert_called_once_with(
        raw_socket,
        server_hostname="policy.example",
    )
    assert tls_context.check_hostname is True
    assert tls_context.verify_mode == ssl.CERT_REQUIRED


def test_private_dns_result_prevents_socket_connection():
    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            return_value=[
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    6,
                    "",
                    ("127.0.0.1", 443),
                )
            ],
        ),
        patch(
            "socket.create_connection",
        ) as connect,
    ):
        with pytest.raises(RetrievalError):
            _download_https_document(
                "https://policy.example/document"
            )

    connect.assert_not_called()


def test_download_deadline_exceeded():
    """Reject a document when the total deadline has expired."""
    from unittest.mock import Mock

    response = FakeResponse(payload=b"Policy text")

    clock = iter([100.0, 113.0])
    tls_context = Mock()
    tls_context.wrap_socket.return_value = Mock()

    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            side_effect=public_dns,
        ),
        patch(
            "ssl.create_default_context",
            return_value=tls_context,
        ),
        patch(
            "time.monotonic",
            side_effect=lambda: next(clock),
        ),
        patch(
            "http.client.HTTPSConnection.request",
            autospec=True,
        ),
        patch(
            "http.client.HTTPSConnection.getresponse",
            return_value=response,
        ),
        patch(
            "http.client.HTTPSConnection.close",
            autospec=True,
        ),
    ):
        with pytest.raises(
            RetrievalError,
            match="deadline exceeded",
        ):
            _download_https_document(
                "https://policy.example/document"
            )


def test_deadline_adjusts_socket_timeout():
    """Use the remaining deadline for the streaming socket."""
    from unittest.mock import Mock

    response = FakeResponse(payload=b"Policy text")

    # Supply sufficient deterministic timestamps for all
    # deadline checks, including the final EOF read.
    clock = iter([100.0, 105.0, 106.0, 107.0, 108.0])
    tls_socket = Mock()
    tls_context = Mock()
    tls_context.wrap_socket.return_value = tls_socket

    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            side_effect=public_dns,
        ),
        patch(
            "ssl.create_default_context",
            return_value=tls_context,
        ),
        patch(
            "time.monotonic",
            side_effect=lambda: next(clock),
        ),
        patch(
            "http.client.HTTPSConnection.request",
            autospec=True,
        ),
        patch(
            "http.client.HTTPSConnection.getresponse",
            return_value=response,
        ),
        patch(
            "http.client.HTTPSConnection.close",
            autospec=True,
        ),
    ):
        result = _download_https_document(
            "https://policy.example/document"
        )

    assert result.payload == b"Policy text"



@pytest.mark.parametrize("unsafe_ip", [
    "127.0.0.1",
    "10.0.0.1",
    "169.254.169.254",
    "224.0.0.1",
    "::1",
])
def test_single_lookup_rejects_unsafe_destination(unsafe_ip):
    """Unsafe DNS answers must never reach the socket."""
    dns_result = [
        (
            socket.AF_INET6 if ":" in unsafe_ip else socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            (unsafe_ip, 443),
        )
    ]

    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            return_value=dns_result,
        ) as dns,
        patch("socket.create_connection") as connect,
    ):
        with pytest.raises(RetrievalError):
            _download_https_document(
                "https://policy.example/document"
            )

    assert dns.call_count == 1
    connect.assert_not_called()


def test_single_lookup_rejects_mixed_dns_answers():
    """One unsafe answer invalidates the entire DNS result."""
    dns_result = [
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

    with (
        patch(
            "app.research_retrieval.socket.getaddrinfo",
            return_value=dns_result,
        ) as dns,
        patch("socket.create_connection") as connect,
    ):
        with pytest.raises(RetrievalError):
            _download_https_document(
                "https://policy.example/document"
            )

    assert dns.call_count == 1
    connect.assert_not_called()
