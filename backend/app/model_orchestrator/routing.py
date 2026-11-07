"""Thread-safe, in-process model routing registry."""

from __future__ import annotations

import os
import threading
from .route_types import ModelRoute

from .runtime import validate_endpoint


class ModelRouter:
    def __init__(self, endpoint: str, model: str):
        self._lock = threading.RLock()
        self._current = ModelRoute(
            validate_endpoint(endpoint), model, 0
        )
        self._previous = None

    def snapshot(self) -> ModelRoute:
        with self._lock:
            return self._current

    def switch(self, endpoint: str, model: str) -> ModelRoute:
        endpoint = validate_endpoint(endpoint)

        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model name is required")

        with self._lock:
            current = self._current

            if current.endpoint == endpoint and current.model == model:
                return current

            self._previous = current
            self._current = ModelRoute(
                endpoint, model, current.generation + 1
            )
            return self._current

    def rollback(self) -> ModelRoute:
        with self._lock:
            if self._previous is None:
                raise RuntimeError("No previous route available")

            previous = self._previous
            current = self._current

            self._current = ModelRoute(
                previous.endpoint,
                previous.model,
                current.generation + 1,
            )
            self._previous = current
            return self._current


def _create_global_router():
    """Select routing mode at process startup."""
    from .router_factory import create_router

    return create_router(
        os.getenv(
            "CIVITAS_LLM_BASE_URL",
            "http://127.0.0.1:42516/v1",
        ),
        os.getenv(
            "CIVITAS_LLM_MODEL",
            "unsloth/Qwen3-1.7B-GGUF:Q4_K_M",
        ),
    )


router = _create_global_router()
