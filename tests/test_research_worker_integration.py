"""Real-process integration tests for isolated retrieval."""

import os
import signal
import subprocess
import sys
import time

import pytest

from app.research_retrieval import RetrievalError


def test_real_child_process_returns_bounded_output(tmp_path):
    """Exercise the same process and temporary-file transport."""
    script = tmp_path / "worker.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write(b'\\x0atext/plainhello')\n"
    )

    output_path = tmp_path / "output.bin"

    with output_path.open("w+b") as output:
        process = subprocess.Popen(
            [sys.executable, str(script)],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        process.wait(timeout=5)

        output.seek(0)
        result = output.read()

    assert process.returncode == 0
    assert result == b"\x0atext/plainhello"


def test_real_child_process_timeout_and_termination(tmp_path):
    """A blocked child is terminated by its process group."""
    script = tmp_path / "sleep_worker.py"
    script.write_text(
        "import time\n"
        "time.sleep(60)\n"
    )

    process = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=0.5)

        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)

        assert process.returncode == -signal.SIGKILL
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
