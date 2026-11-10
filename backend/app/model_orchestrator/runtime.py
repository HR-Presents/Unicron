"""Read-only health monitoring for local inference servers."""

from __future__ import annotations

import ipaddress
import json
import urllib.parse
import urllib.request
import urllib.error


def validate_endpoint(endpoint: str) -> str:
    parsed = urllib.parse.urlsplit(endpoint)

    if parsed.scheme != "http":
        raise ValueError("Only local HTTP endpoints are supported")

    if parsed.username or parsed.password:
        raise ValueError("Credentials in endpoint URLs are forbidden")

    if parsed.query or parsed.fragment:
        raise ValueError("Query strings and fragments are forbidden")

    if parsed.path.rstrip("/") != "/v1":
        raise ValueError("Endpoint must use /v1")

    if parsed.port is None:
        raise ValueError("Explicit port required")

    try:
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError as exc:
        raise ValueError("Numeric loopback address required") from exc

    if address != ipaddress.ip_address("127.0.0.1"):
        raise ValueError("Only 127.0.0.1 is permitted")

    return f"http://127.0.0.1:{parsed.port}/v1"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        raise ValueError("HTTP redirects are not permitted")


def probe_runtime(
    endpoint: str = "http://127.0.0.1:42516/v1",
    model: str = "unicron-qwen",
) -> dict:
    endpoint = validate_endpoint(endpoint)

    result = {
        "endpoint": endpoint,
        "model": model,
        "reachable": False,
        "model_available": False,
        "inference_passed": False,
        "error": None,
    }

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
    )

    try:
        with opener.open(endpoint + "/models", timeout=5) as response:
            payload = json.load(response)

        result["reachable"] = True

        models = [
            item.get("id")
            for item in payload.get("data", [])
            if isinstance(item, dict)
        ]

        result["model_available"] = model in models

        if not result["model_available"]:
            return result

        request_payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with READY. /no_think",
                }
            ],
            "temperature": 0,
            "max_tokens": 32,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        request = urllib.request.Request(
            endpoint + "/chat/completions",
            data=json.dumps(request_payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with opener.open(request, timeout=30) as response:
            completion = json.load(response)

        choices = completion.get("choices", [])
        content = (
            choices[0].get("message", {}).get("content")
            if choices else None
        )

        result["inference_passed"] = (
            isinstance(content, str)
            and bool(content.strip())
        )

    except (OSError, ValueError, TypeError, KeyError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


if __name__ == "__main__":
    print(json.dumps(probe_runtime(), indent=2))
