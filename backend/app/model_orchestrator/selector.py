"""Read-only model candidate evaluation."""

import json

from .catalog import CATALOG
from .hardware import detect_hardware


def recommend(hardware=None):
    if hardware is None:
        hardware = detect_hardware()

    gpu_vram = max(
        (gpu.get("vram_total_mib", 0) for gpu in hardware["gpus"]),
        default=0,
    ) / 1024

    active_models = (
        set(hardware["inference"].get("models", []))
        if hardware["inference"].get("reachable")
        else set()
    )

    candidates = []

    for model in CATALOG:
        active = bool(
            model.served_name
            and model.served_name in active_models
        )

        if active:
            status = "reuse_active_endpoint"
        elif not hardware["runtimes"].get(model.runtime, False):
            status = "runtime_unavailable"
        elif model.estimated_vram_gib > gpu_vram:
            status = "estimated_vram_insufficient"
        else:
            status = "requires_validation"

        candidates.append({
            "model": model.model_id,
            "runtime": model.runtime,
            "estimated_vram_gib": model.estimated_vram_gib,
            "status": status,
            "active": active,
        })

    selected = next(
        (candidate for candidate in candidates if candidate["active"]),
        None,
    )

    return {
        "selected": selected,
        "candidates": candidates,
        "automatic_switch_performed": False,
    }


if __name__ == "__main__":
    print(json.dumps(recommend(), indent=2))
