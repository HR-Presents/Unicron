"""Guarded, explicitly approved model route activation."""

from __future__ import annotations

import threading

from .routing import ModelRouter
from .runtime import validate_endpoint, probe_runtime
from .compatibility import check_compatibility


_activation_lock = threading.RLock()


def activate_model(
    endpoint: str,
    model: str,
    *,
    approved: bool = False,
    model_router: ModelRouter | None = None,
) -> dict:
    """Validate a model before atomically changing its default route."""

    if approved is not True:
        raise PermissionError("Explicit approval required")

    endpoint = validate_endpoint(endpoint)

    if not isinstance(model, str) or not model.strip():
        raise ValueError("A nonempty model name is required")

    from .routing import router as global_router
    selected_router = model_router if model_router is not None else global_router

    with _activation_lock:
        previous = selected_router.snapshot()

        probe = probe_runtime(endpoint=endpoint, model=model)

        if not (
            probe.get("reachable")
            and probe.get("model_available")
            and probe.get("inference_passed")
        ):
            return {
                "activated": False,
                "reason": "runtime_validation_failed",
                "previous_model": previous.model,
            }

        compatibility = check_compatibility(
            endpoint=endpoint,
            model=model,
        )

        if not compatibility.get("compatible"):
            return {
                "activated": False,
                "reason": "compatibility_validation_failed",
                "previous_model": previous.model,
            }

        current = selected_router.switch(endpoint, model)

        return {
            "activated": True,
            "previous_model": previous.model,
            "model": current.model,
            "endpoint": current.endpoint,
            "generation": current.generation,
        }
