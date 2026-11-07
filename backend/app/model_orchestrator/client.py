"""Shared OpenAI-compatible local inference transport."""

from __future__ import annotations

import json
import urllib.request

from .routing import ModelRoute
from .pinning import current_route
from .runtime import NoRedirect, validate_endpoint


def completion(payload: dict, *, route: ModelRoute | None = None,
               timeout: float = 120) -> dict:
    """Send one completion using a consistent model route snapshot."""

    selected = route if route is not None else current_route()
    endpoint = validate_endpoint(selected.endpoint)

    if not isinstance(selected.model, str) or not selected.model.strip():
        raise ValueError("Invalid selected model")

    if not isinstance(payload, dict):
        raise TypeError("Payload must be a dictionary")

    request_payload = {
        **payload,
        "model": selected.model,
    }

    request = urllib.request.Request(
        endpoint + "/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
    )

    with opener.open(request, timeout=timeout) as response:
        return json.load(response)
