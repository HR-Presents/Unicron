"""Read-only pre-activation checks for local inference models."""

from __future__ import annotations

import json

from .compatibility import check_compatibility
from .runtime import probe_runtime, validate_endpoint


def evaluate_activation(
    endpoint: str = "http://127.0.0.1:42516/v1",
    model: str = "unicron-qwen",
) -> dict:
    endpoint = validate_endpoint(endpoint)

    health = probe_runtime(endpoint, model)

    result = {
        "endpoint": endpoint,
        "model": model,
        "health": health,
        "compatibility": None,
        "activation_allowed": False,
        "activation_performed": False,
        "reason": None,
    }

    if not all((
        health["reachable"],
        health["model_available"],
        health["inference_passed"],
    )):
        result["reason"] = "Runtime health check failed"
        return result

    compatibility = check_compatibility(endpoint, model)
    result["compatibility"] = compatibility

    if not compatibility["compatible"]:
        result["reason"] = "Structured-output check failed"
        return result

    result["activation_allowed"] = True
    result["reason"] = "Pre-activation checks passed"
    return result


if __name__ == "__main__":
    print(json.dumps(evaluate_activation(), indent=2))
