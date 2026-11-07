"""Read-only structural validation of cached Hugging Face models."""

from __future__ import annotations

import json
from pathlib import Path

from .installer import plan_install


REQUIRED_FILES = (
    "config.json",
    "tokenizer_config.json",
)

WEIGHT_EXTENSIONS = (".safetensors",)


def validate_snapshot(snapshot: str | Path) -> dict:
    root = Path(snapshot)

    missing = []
    broken_links = []
    weight_files = []
    empty_files = []

    for name in REQUIRED_FILES:
        if not (root / name).is_file():
            missing.append(name)

    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_symlink() and not path.exists():
                broken_links.append(str(path.relative_to(root)))

            if path.name.endswith(WEIGHT_EXTENSIONS):
                weight_files.append(path.name)
                if not path.is_file() or path.stat().st_size == 0:
                    empty_files.append(path.name)

    valid = (
        root.is_dir()
        and not missing
        and not broken_links
        and bool(weight_files)
        and not empty_files
    )

    return {
        "snapshot": str(root),
        "structurally_valid": valid,
        "required_files_missing": missing,
        "broken_symlinks": broken_links,
        "weight_files": weight_files,
        "empty_weight_files": empty_files,
        "cryptographic_integrity_verified": False,
        "load_test_passed": False,
    }


def validate_cached_model(model_id: str) -> dict:
    plan = plan_install(model_id)
    root = Path(plan["cache_directory"]) / "snapshots"

    return {
        "model_id": model_id,
        "snapshots": [
            validate_snapshot(root / name)
            for name in plan["cached_snapshots"]
        ],
    }


if __name__ == "__main__":
    print(json.dumps(
        validate_cached_model("Qwen/Qwen3-1.7B"),
        indent=2,
    ))
