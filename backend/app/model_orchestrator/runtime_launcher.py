"""Approval-gated vLLM launch planning. No process execution."""

from __future__ import annotations

from pathlib import Path

from .installer import APPROVED_MODELS
from .startup_preflight import startup_preflight


def plan_runtime_launch(
    model_id: str,
    snapshot: str | Path,
    *,
    served_name: str,
    port: int = 42517,
    approved: bool = False,
    runtime_executable: str | Path = (
        "/home/haziq/unicron-model-venv/bin/vllm"
    ),
    max_model_len: int = 4096,
    gpu_memory_utilization: float = 0.75,
) -> dict:
    if approved is not True:
        raise PermissionError("Explicit launch approval required")

    if model_id not in APPROVED_MODELS:
        raise ValueError("Model is not approved")

    if (
        not isinstance(served_name, str)
        or not served_name.strip()
        or len(served_name) > 100
        or any(c not in "abcdefghijklmnopqrstuvwxyz"
               "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
               for c in served_name)
    ):
        raise ValueError("Invalid served model name")

    if (
        not isinstance(max_model_len, int)
        or isinstance(max_model_len, bool)
        or not 256 <= max_model_len <= 32768
    ):
        raise ValueError("Invalid context length")

    if (
        not isinstance(gpu_memory_utilization, (int, float))
        or isinstance(gpu_memory_utilization, bool)
        or not 0.1 <= gpu_memory_utilization <= 0.9
    ):
        raise ValueError("Invalid GPU utilization")

    preflight = startup_preflight(
        model_id,
        snapshot,
        port=port,
        runtime_executable=runtime_executable,
    )

    if not preflight["ready"]:
        return {
            "approved": True,
            "ready": False,
            "preflight": preflight,
            "command": None,
            "started": False,
        }

    command = [
        str(Path(runtime_executable).expanduser()),
        "serve",
        str(Path(snapshot).expanduser().resolve()),
        "--served-model-name",
        served_name,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--dtype",
        "auto",
        "--max-model-len",
        str(max_model_len),
        "--gpu-memory-utilization",
        str(gpu_memory_utilization),
        "--max-num-seqs",
        "2",
    ]

    return {
        "approved": True,
        "ready": True,
        "preflight": preflight,
        "command": command,
        "started": False,
    }
