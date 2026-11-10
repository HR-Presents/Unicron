"""Compatibility transport for incremental agent migration."""

from __future__ import annotations

import json
import urllib.request

from .routing import ModelRoute, router
from .runtime import validate_endpoint


def completion_legacy(
    payload: dict,
    *,
    route: ModelRoute | None = None,
    timeout: float = 120,
    open_request=None,
    load_response=None,
) -> dict:
    """Use a route snapshot while preserving injectable legacy I/O."""

    selected = route if route is not None else router.snapshot()
    endpoint = validate_endpoint(selected.endpoint)

    if not isinstance(selected.model, str) or not selected.model.strip():
        raise ValueError("Invalid selected model")

    if not isinstance(payload, dict):
        raise TypeError("Payload must be a dictionary")

    body = {**payload, "model": selected.model}

    request = urllib.request.Request(
        endpoint + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    opener = open_request if open_request is not None else urllib.request.urlopen
    loader = load_response if load_response is not None else json.load

    with opener(request, timeout=timeout) as response:
        return loader(response)
