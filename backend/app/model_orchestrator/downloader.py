"""Approval-gated, revision-pinned Hugging Face model downloads."""

from __future__ import annotations

import re
from pathlib import Path

from .installer import APPROVED_MODELS


REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def download_model(
    model_id: str,
    revision: str,
    *,
    approved: bool = False,
    cache_dir: str | Path | None = None,
) -> dict:
    if model_id not in APPROVED_MODELS:
        raise ValueError("Model is not approved")

    if not REVISION_PATTERN.fullmatch(revision):
        raise ValueError("A full 40-character commit revision is required")

    if approved is not True:
        raise PermissionError("Explicit download approval is required")

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub must be installed before downloading"
        ) from exc

    model = APPROVED_MODELS[model_id]

    options = {
        "repo_id": model["repository"],
        "revision": revision,
        "allow_patterns": [
            "*.json",
            "*.safetensors",
            "*.model",
            "*.txt",
            "*.jinja",
            "LICENSE*",
            "README*",
        ],
    }

    if cache_dir is not None:
        options["cache_dir"] = str(Path(cache_dir).expanduser())

    snapshot = snapshot_download(**options)

    return {
        "model_id": model_id,
        "revision": revision,
        "snapshot": snapshot,
        "download_completed": True,
        "activated": False,
    }
