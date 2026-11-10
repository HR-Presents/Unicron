"""Isolated, deadline-bound execution of untrusted HTTPS retrieval."""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from .research_retrieval import (
    MAX_DOCUMENT_BYTES,
    RetrievalError,
    RetrievedDocument,
    _validate_https_url_syntax,
)

WORKER_TIMEOUT_SECONDS = 15
MAX_WORKER_OUTPUT_BYTES = MAX_DOCUMENT_BYTES + 4096


def _worker_main() -> None:
    """Run one retrieval and write a bounded binary response."""
    import resource
    import struct

    # Apply limits inside the isolated child, before network access.
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (MAX_WORKER_OUTPUT_BYTES, MAX_WORKER_OUTPUT_BYTES),
    )

    from .research_retrieval import _download_https_document

    url = sys.stdin.buffer.read(4096).decode("utf-8")
    document = _download_https_document(url)

    content_type = document.content_type.encode("ascii")
    if len(content_type) > 255:
        raise RetrievalError("Invalid content type")

    output = (
        struct.pack("!B", len(content_type))
        + content_type
        + document.payload
    )

    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


def retrieve_isolated(url: str) -> RetrievedDocument:
    """Retrieve through a killable child process with a hard deadline."""
    _validate_https_url_syntax(url)

    command = [
        sys.executable,
        "-m",
        f"{__package__}.research_worker",
        "--child",
    ]

    import tempfile

    with tempfile.TemporaryFile() as output_file:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=output_file,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise RetrievalError(
                "Unable to start isolated retrieval worker"
            ) from exc

        try:
            process.communicate(
                input=url.encode("utf-8"),
                timeout=WORKER_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

            process.communicate()

            raise RetrievalError(
                "Isolated document retrieval timed out"
            ) from exc

        output_file.seek(0, os.SEEK_END)
        output_size = output_file.tell()

        if output_size > MAX_WORKER_OUTPUT_BYTES:
            raise RetrievalError(
                "Isolated retrieval output exceeds permitted size"
            )

        output_file.seek(0)
        output = output_file.read(MAX_WORKER_OUTPUT_BYTES + 1)

    if process.returncode != 0:
        raise RetrievalError("Isolated document retrieval failed")

    if not output or len(output) > MAX_WORKER_OUTPUT_BYTES:
        raise RetrievalError("Invalid isolated retrieval response")

    header_length = output[0]
    if header_length == 0 or len(output) <= 1 + header_length:
        raise RetrievalError("Invalid isolated retrieval header")

    try:
        content_type = output[1:1 + header_length].decode("ascii")
    except UnicodeDecodeError as exc:
        raise RetrievalError("Invalid content type") from exc

    payload = output[1 + header_length:]

    if len(payload) > MAX_DOCUMENT_BYTES:
        raise RetrievalError("Document exceeds permitted size")

    return RetrievedDocument(
        url=url,
        content_type=content_type,
        payload=payload,
    )


if __name__ == "__main__":
    if sys.argv[1:] != ["--child"]:
        raise SystemExit(2)
    _worker_main()
