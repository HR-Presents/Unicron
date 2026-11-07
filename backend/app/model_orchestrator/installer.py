"""Safe model installation planning; no network or download operations."""

from __future__ import annotations

import json
from pathlib import Path


APPROVED_MODELS = {
    "Qwen/Qwen3-1.7B": {
        "runtime": "vllm",
        "repository": "Qwen/Qwen3-1.7B",
        "format": "safetensors",
    },
    "Qwen/Qwen3-4B": {
        "runtime": "vllm",
        "repository": "Qwen/Qwen3-4B",
        "format": "safetensors",
    },
}


def plan_install(
    model_id: str,
    cache_root: str | Path | None = None,
) -> dict:
    if model_id not in APPROVED_MODELS:
        raise ValueError("Model is not in the approved catalog")

    model = APPROVED_MODELS[model_id]

    root = (
        Path(cache_root).expanduser()
        if cache_root is not None
        else Path.home() / ".cache/huggingface/hub"
    )

    repository_dir = root / (
        "models--" + model["repository"].replace("/", "--")
    )

    snapshots_dir = repository_dir / "snapshots"

    snapshots = (
        sorted(
            path.name
            for path in snapshots_dir.iterdir()
            if path.is_dir()
        )
        if snapshots_dir.is_dir()
        else []
    )

    return {
        "model_id": model_id,
        "runtime": model["runtime"],
        "format": model["format"],
        "cache_directory": str(repository_dir),
        "cached_snapshots": snapshots,
        "download_required": not bool(snapshots),
        "approval_required": True,
        "download_started": False,
    }


if __name__ == "__main__":
    print(json.dumps(
        plan_install("Qwen/Qwen3-1.7B"),
        indent=2,
    ))
