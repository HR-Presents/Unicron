"""Regression test for a worker surviving its managed parent."""

import os
import signal
import sys
import time

from pathlib import Path

from backend.app.model_orchestrator.process_manager import ProcessManager


def test_parent_exit_does_not_leave_worker_running(tmp_path):
    manager = ProcessManager()
    pid_file = tmp_path / "worker.pid"

    parent_code = """
import subprocess
import sys
from pathlib import Path

worker = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(30)"],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
Path(sys.argv[1]).write_text(str(worker.pid))
"""

    parent = manager.start(
        [sys.executable, "-c", parent_code, str(pid_file)],
        approved=True,
    )

    worker_pid = None

    try:
        for _ in range(100):
            if pid_file.exists():
                break
            time.sleep(0.05)

        assert pid_file.exists(), "Worker PID was not recorded"

        worker_pid = int(pid_file.read_text())

        # Wait until the managed parent has exited.
        for _ in range(100):
            if not manager.status(parent.pid)["running"]:
                break
            time.sleep(0.05)

        assert not manager.status(parent.pid)["running"]

        manager.stop(parent.pid, approved=True)

        # An exited process may remain temporarily as a zombie.
        for _ in range(40):
            try:
                state = Path(
                    f"/proc/{worker_pid}/stat"
                ).read_text().split()[2]
            except FileNotFoundError:
                return

            if state == "Z":
                return

            time.sleep(0.05)

        raise AssertionError(
            "Managed worker survived parent shutdown"
        )

    finally:
        # Test-only cleanup: target only the worker created here.
        if worker_pid is not None:
            try:
                os.kill(worker_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
