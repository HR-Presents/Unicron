"""Regression test for SIGTERM-resistant workers."""

import os
import signal
import sys
import time
from pathlib import Path

from backend.app.model_orchestrator.process_manager import ProcessManager


def test_stubborn_worker_is_terminated(tmp_path):
    manager = ProcessManager()
    pid_file = tmp_path / "worker.pid"
    ready_file = tmp_path / "worker.ready"

    worker_code = (
        "import signal, time, sys\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text('ready')\n"
        "while True: time.sleep(1)\n"
    )

    parent_code = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        "worker = subprocess.Popen("
        "[sys.executable, '-c', sys.argv[3], sys.argv[2]], "
        "stdin=subprocess.DEVNULL, "
        "stdout=subprocess.DEVNULL, "
        "stderr=subprocess.DEVNULL)\n"
        "Path(sys.argv[1]).write_text(str(worker.pid))\n"
    )

    parent = manager.start(
        [
            sys.executable,
            "-c",
            parent_code,
            str(pid_file),
            str(ready_file),
            worker_code,
        ],
        approved=True,
    )

    worker_pid = None

    try:
        for _ in range(100):
            if pid_file.exists() and ready_file.exists():
                break
            time.sleep(0.05)

        assert pid_file.exists()
        assert ready_file.exists()

        worker_pid = int(pid_file.read_text())

        for _ in range(100):
            if not manager.status(parent.pid)["running"]:
                break
            time.sleep(0.05)

        assert not manager.status(parent.pid)["running"]

        manager.stop(parent.pid, approved=True, timeout=0.2)

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
            "SIGTERM-resistant managed worker survived shutdown"
        )

    finally:
        if worker_pid is not None:
            try:
                os.kill(worker_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
