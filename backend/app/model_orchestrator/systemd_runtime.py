"""Isolated, user-level systemd runtime lifecycle management."""

from __future__ import annotations

import re
import subprocess
import uuid


class SystemdRuntimeManager:
    """Manage only units created and recorded by this instance."""

    def __init__(self):
        self._owned_units: set[str] = set()

    @staticmethod
    def _run(args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def start(
        self,
        command: list[str],
        *,
        approved: bool = False,
    ) -> str:
        if approved is not True:
            raise PermissionError("Explicit startup approval required")

        if (
            not isinstance(command, list)
            or not command
            or not all(isinstance(x, str) and x for x in command)
        ):
            raise ValueError("Invalid command")

        # Initial test-only restriction. Real model launch commands
        # will require a separate validated integration layer.
        if command[0] != "/usr/bin/python3":
            raise ValueError("Executable not allowed in test mode")

        unit = f"unicron-managed-{uuid.uuid4().hex}.service"

        self._run([
            "systemd-run",
            "--user",
            f"--unit={unit}",
            "--property=Type=exec",
            "--property=KillMode=control-group",
            "--property=TimeoutStopSec=5",
            "--",
            *command,
        ])

        self._owned_units.add(unit)
        return unit

    def status(self, unit: str) -> dict:
        if unit not in self._owned_units:
            raise ValueError("Unit is not owned by this manager")

        result = self._run([
            "systemctl",
            "--user",
            "--no-pager",
            "show",
            unit,
            "--property=ActiveState",
            "--property=SubState",
            "--property=MainPID",
        ])

        fields = {}

        for line in result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                fields[key] = value

        return fields

    def stop(
        self,
        unit: str,
        *,
        approved: bool = False,
    ) -> dict:
        if approved is not True:
            raise PermissionError("Explicit shutdown approval required")

        if unit not in self._owned_units:
            raise ValueError("Unit is not owned by this manager")

        self._run([
            "systemctl",
            "--user",
            "--no-pager",
            "stop",
            unit,
        ])

        return self.status(unit)
