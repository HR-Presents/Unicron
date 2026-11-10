"""End-to-end tests of the real isolated retrieval subprocess."""

import subprocess
import sys

import pytest

from app.research_retrieval import RetrievalError
from app import research_worker


URL = "https://policy.example/document"


def test_real_isolated_worker_success(tmp_path, monkeypatch):
    script = tmp_path / "success.py"
    script.write_text(
        "import sys\n"
        "sys.stdin.buffer.read()\n"
        "sys.stdout.buffer.write("
        "bytes([10]) + b'text/plain' + b'evidence')\n"
    )

    original_popen = subprocess.Popen

    def launch(command, **kwargs):
        return original_popen(
            [sys.executable, str(script)],
            **kwargs,
        )

    monkeypatch.setattr(
        research_worker.subprocess,
        "Popen",
        launch,
    )

    result = research_worker.retrieve_isolated(URL)

    assert result.url == URL
    assert result.content_type == "text/plain"
    assert result.payload == b"evidence"
    assert result.verification_status == "unverified"


def test_real_isolated_worker_timeout(tmp_path, monkeypatch):
    script = tmp_path / "blocked.py"
    script.write_text(
        "import time\n"
        "time.sleep(60)\n"
    )

    original_popen = subprocess.Popen

    def launch(command, **kwargs):
        return original_popen(
            [sys.executable, str(script)],
            **kwargs,
        )

    monkeypatch.setattr(
        research_worker.subprocess,
        "Popen",
        launch,
    )

    monkeypatch.setattr(
        research_worker,
        "WORKER_TIMEOUT_SECONDS",
        0.3,
    )

    with pytest.raises(
        RetrievalError,
        match="timed out",
    ):
        research_worker.retrieve_isolated(URL)
