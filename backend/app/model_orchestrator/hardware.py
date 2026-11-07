"""Read-only hardware and inference-runtime discovery for UNICRON."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_MODEL_ENDPOINT = "http://127.0.0.1:42516/v1"


def _command(args: list[str], timeout: int = 5) -> str | None:
    try:
        return subprocess.check_output(
            args,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _memory() -> dict:
    if platform.system() != "Linux":
        return {"total_bytes": None, "available_bytes": None}

    try:
        values = {}
        with open("/proc/meminfo", encoding="utf-8") as file:
            for line in file:
                key, value = line.split(":", 1)
                values[key] = int(value.strip().split()[0]) * 1024

        return {
            "total_bytes": values.get("MemTotal"),
            "available_bytes": values.get("MemAvailable"),
        }
    except (OSError, ValueError):
        return {"total_bytes": None, "available_bytes": None}


def _cpu_name() -> str:
    if platform.system() == "Linux":
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as file:
                for line in file:
                    if line.startswith("model name"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass

    return platform.processor() or "unknown"


def _nvidia_gpus() -> list[dict]:
    output = _command([
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    ])

    if not output:
        return []

    devices = []

    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]

        if len(parts) != 5:
            continue

        try:
            index, name, total, free, driver = parts
            devices.append({
                "index": int(index),
                "vendor": "NVIDIA",
                "name": name,
                "vram_total_mib": int(total),
                "vram_free_mib": int(free),
                "driver_version": driver,
            })
        except ValueError:
            continue

    return devices


def _active_models(endpoint: str) -> dict:
    url = endpoint.rstrip("/") + "/models"

    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.load(response)

        models = [
            item["id"]
            for item in payload.get("data", [])
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
        ]

        return {
            "reachable": True,
            "models": models,
        }
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
    ):
        return {
            "reachable": False,
            "models": [],
        }


def detect_hardware(endpoint: str | None = None) -> dict:
    """Discover local hardware without changing system state."""

    endpoint = endpoint or os.getenv(
        "CIVITAS_LLM_BASE_URL",
        DEFAULT_MODEL_ENDPOINT,
    )

    vllm_path = Path.home() / "unicron-model-venv/bin/vllm"

    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
        },
        "cpu": {
            "name": _cpu_name(),
            "logical_cores": os.cpu_count(),
        },
        "memory": _memory(),
        "gpus": _nvidia_gpus(),
        "runtimes": {
            "vllm": bool(shutil.which("vllm") or vllm_path.is_file()),
            "llama_cpp": shutil.which("llama-server") is not None,
            "ollama": shutil.which("ollama") is not None,
        },
        "inference": {
            "endpoint": endpoint,
            **_active_models(endpoint),
        },
    }


if __name__ == "__main__":
    print(json.dumps(detect_hardware(), indent=2))
