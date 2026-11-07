"""Track and stop only child processes launched by this manager."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagedProcess:
    pid: int
    command: tuple[str, ...]


class ProcessManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._processes: dict[int, subprocess.Popen] = {}

    def start(
        self,
        command: list[str],
        *,
        approved: bool = False,
        cwd: str | Path | None = None,
    ) -> ManagedProcess:
        if approved is not True:
            raise PermissionError("Explicit process-start approval required")

        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(item, str) and item for item in command)
        ):
            raise ValueError("Invalid process command")

        with self._lock:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            self._processes[process.pid] = process

            return ManagedProcess(
                pid=process.pid,
                command=tuple(command),
            )

    def status(self, pid: int) -> dict:
        with self._lock:
            process = self._processes.get(pid)

            if process is None:
                return {"managed": False, "running": False}

            return {
                "managed": True,
                "running": process.poll() is None,
                "returncode": process.poll(),
            }

    def stop(
        self,
        pid: int,
        *,
        approved: bool = False,
        timeout: float = 5.0,
    ) -> dict:
        if approved is not True:
            raise PermissionError("Explicit process-stop approval required")

        with self._lock:
            process = self._processes.get(pid)

            if process is None:
                raise ValueError("Process is not owned by this manager")

            # start_new_session=True establishes a dedicated process
            # group whose initial PGID equals the launched child PID.
            # A worker may survive even after its parent exits.
            pgid = process.pid

            if process.poll() is None:
                actual_pgid = os.getpgid(process.pid)

                if actual_pgid != pgid:
                    raise RuntimeError(
                        "Managed process group identity mismatch"
                    )

            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError("Shutdown timeout must be positive")

            def active_group_members(group_id: int) -> list[int]:
                members = []

                for entry in Path("/proc").iterdir():
                    if not entry.name.isdigit():
                        continue

                    try:
                        stat = (entry / "stat").read_text()
                        fields = stat[stat.rfind(")") + 2:].split()

                        state = fields[0]
                        process_group = int(fields[2])

                        if process_group == group_id and state not in ("Z", "X"):
                            members.append(int(entry.name))
                    except (OSError, ValueError, IndexError):
                        continue

                return members

            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass

            deadline = time.monotonic() + timeout

            while time.monotonic() < deadline:
                if not active_group_members(pgid):
                    break
                time.sleep(0.05)

            if active_group_members(pgid):
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                raise RuntimeError(
                    "Managed parent did not exit after shutdown"
                )

            return {
                "managed": True,
                "running": False,
                "returncode": process.returncode,
            }


manager = ProcessManager()
