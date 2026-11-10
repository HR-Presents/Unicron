"""Read-only preflight for launching a local vLLM model."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
from pathlib import Path

from .cache_validator import validate_snapshot
from .catalog import CATALOG
from .installer import APPROVED_MODELS


def gpu_memory_mib() -> dict:
    command = [
        "nvidia-smi",
        "--query-gpu=memory.total,memory.used,memory.free",
        "--format=csv,noheader,nounits",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )

    rows = [
        row.strip()
        for row in result.stdout.splitlines()
        if row.strip()
    ]

    if len(rows) != 1:
        raise RuntimeError(
            "Exactly one NVIDIA GPU is required"
        )

    values = [int(value.strip()) for value in rows[0].split(",")]

    if len(values) != 3:
        raise RuntimeError("Unexpected GPU memory response")

    return dict(zip(("total", "used", "free"), values))


def port_available(port: int) -> bool:
    if not isinstance(port, int) or isinstance(port, bool):
        raise ValueError("Port must be an integer")

    if not 1024 <= port <= 65535:
        raise ValueError("Port must be between 1024 and 65535")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False

    return True


def startup_preflight(
    model_id: str,
    snapshot: str | Path,
    *,
    port: int = 42517,
    runtime_executable: str | Path = (
        "/home/haziq/unicron-model-venv/bin/vllm"
    ),
    reserve_mib: int = 512,
) -> dict:
    if model_id not in APPROVED_MODELS:
        raise ValueError("Model is not approved")

    if not isinstance(reserve_mib, int) or reserve_mib < 0:
        raise ValueError("Invalid GPU memory reserve")

    candidate = next(
        (item for item in CATALOG if item.model_id == model_id),
        None,
    )

    if candidate is None or candidate.runtime != "vllm":
        raise ValueError("No supported vLLM candidate")

    executable = Path(runtime_executable).expanduser()
    executable_ready = (
        executable.is_file()
        and executable.stat().st_mode & 0o111 != 0
    )

    snapshot_result = validate_snapshot(snapshot)

    try:
        gpu = gpu_memory_mib()
        gpu_error = None
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        gpu = None
        gpu_error = type(exc).__name__

    required_mib = int(
        candidate.estimated_vram_gib * 1024 + 0.999
    )

    memory_ready = (
        gpu is not None
        and gpu["free"] >= required_mib + reserve_mib
    )

    port_ready = port_available(port)

    disk_root = Path(snapshot).expanduser().resolve()

    while not disk_root.exists():
        parent = disk_root.parent
        if parent == disk_root:
            raise RuntimeError(
                "No existing directory available for disk-space check"
            )
        disk_root = parent

    disk = shutil.disk_usage(disk_root)

    checks = {
        "runtime_executable": bool(executable_ready),
        "snapshot_structurally_valid": bool(
            snapshot_result["structurally_valid"]
        ),
        "gpu_memory_sufficient": bool(memory_ready),
        "port_available": bool(port_ready),
    }

    return {
        "model_id": model_id,
        "port": port,
        "checks": checks,
        "ready": all(checks.values()),
        "gpu": gpu,
        "gpu_error": gpu_error,
        "estimated_required_vram_mib": required_mib,
        "reserve_mib": reserve_mib,
        "disk_free_gib": round(
            disk.free / (1024 ** 3), 2
        ),
        "started": False,
        "activated": False,
    }


if __name__ == "__main__":
    snapshot = (
        Path.home()
        / ".cache/huggingface/hub/models--Qwen--Qwen3-1.7B"
        / "snapshots"
        / "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    )

    print(json.dumps(
        startup_preflight(
            "Qwen/Qwen3-1.7B",
            snapshot,
        ),
        indent=2,
    ))
