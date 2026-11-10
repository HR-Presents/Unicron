"""Tests for the isolated research retrieval boundary."""

import os
import signal
import subprocess
from unittest.mock import Mock, patch

import pytest

from app.research_retrieval import RetrievalError
from app.research_worker import (
    MAX_WORKER_OUTPUT_BYTES,
    retrieve_isolated,
)


URL = "https://policy.example/document"


def fake_process(output, returncode=0):
    """Write simulated worker output to its assigned file."""
    def start(command, **kwargs):
        assert command[-1] == "--child"
        assert kwargs["start_new_session"] is True

        output_target = kwargs["stdout"]
        output_target.write(output)
        output_target.flush()

        process = Mock()
        process.pid = 12345
        process.returncode = returncode
        process.communicate.return_value = (None, None)
        return process

    return start


def test_successful_isolated_retrieval():
    payload = b"Government policy evidence"
    content_type = b"text/plain"
    output = bytes([len(content_type)]) + content_type + payload

    with patch(
        "app.research_worker.subprocess.Popen",
        side_effect=fake_process(output),
    ) as start:
        result = retrieve_isolated(URL)

    assert start.call_count == 1
    assert result.url == URL
    assert result.content_type == "text/plain"
    assert result.payload == payload
    assert result.verification_status == "unverified"


def test_nonzero_worker_exit_rejected():
    with patch(
        "app.research_worker.subprocess.Popen",
        side_effect=fake_process(b"", returncode=1),
    ):
        with pytest.raises(RetrievalError):
            retrieve_isolated(URL)


@pytest.mark.parametrize("output", [
    b"",
    b"\x00",
    b"\x0atext/plain",
    b"\x05abc",
    b"\x01\xffpayload",
])
def test_malformed_worker_output_rejected(output):
    with patch(
        "app.research_worker.subprocess.Popen",
        side_effect=fake_process(output),
    ):
        with pytest.raises(RetrievalError):
            retrieve_isolated(URL)


def test_oversized_worker_output_rejected():
    output = b"x" * (MAX_WORKER_OUTPUT_BYTES + 1)

    with patch(
        "app.research_worker.subprocess.Popen",
        side_effect=fake_process(output),
    ):
        with pytest.raises(RetrievalError):
            retrieve_isolated(URL)


def test_worker_timeout_terminates_process_group():
    def start(command, **kwargs):
        process = Mock()
        process.pid = 12345
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(command, 15),
            (None, None),
        ]
        return process

    with (
        patch(
            "app.research_worker.subprocess.Popen",
            side_effect=start,
        ),
        patch(
            "app.research_worker.os.killpg",
        ) as kill_group,
    ):
        with pytest.raises(
            RetrievalError,
            match="timed out",
        ):
            retrieve_isolated(URL)

    kill_group.assert_called_once_with(
        12345, signal.SIGKILL
    )


def test_invalid_url_does_not_start_worker():
    with patch(
        "app.research_worker.subprocess.Popen"
    ) as start:
        with pytest.raises(RetrievalError):
            retrieve_isolated(
                "http://127.0.0.1/private"
            )

    start.assert_not_called()


def test_worker_launch_failure_returns_retrieval_error():
    with patch(
        "app.research_worker.subprocess.Popen",
        side_effect=OSError("Process creation failed"),
    ):
        with pytest.raises(
            RetrievalError,
            match="Unable to start isolated retrieval worker",
        ):
            retrieve_isolated(URL)
