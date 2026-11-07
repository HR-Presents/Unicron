"""Structured-output compatibility checks for local inference."""

from __future__ import annotations

import json
import time
import urllib.request

from .runtime import NoRedirect, validate_endpoint


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "risk_level"],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["ready"],
        },
        "risk_level": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
    },
}


def check_compatibility(
    endpoint: str = "http://127.0.0.1:42516/v1",
    model: str = "unicron-qwen",
) -> dict:
    endpoint = validate_endpoint(endpoint)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Return only JSON matching the supplied schema.",
            },
            {
                "role": "user",
                "content": (
                    "Classify an AI system deployed without "
                    "documented human oversight. /no_think"
                ),
            },
        ],
        "temperature": 0,
        "max_tokens": 96,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "unicron_compatibility",
                "strict": True,
                "schema": SCHEMA,
            },
        },
    }

    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        NoRedirect(),
    )

    request = urllib.request.Request(
        endpoint + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()

    try:
        with opener.open(request, timeout=60) as response:
            result = json.load(response)

        latency = round(time.perf_counter() - start, 3)
        choice = result["choices"][0]
        output = json.loads(choice["message"]["content"])

        valid = (
            choice.get("finish_reason") == "stop"
            and set(output) == {"status", "risk_level"}
            and output["status"] == "ready"
            and output["risk_level"] in ("low", "medium", "high")
        )

        return {
            "model": model,
            "compatible": valid,
            "latency_seconds": latency,
            "output": output,
            "error": None,
        }

    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return {
            "model": model,
            "compatible": False,
            "latency_seconds": None,
            "output": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


if __name__ == "__main__":
    print(json.dumps(check_compatibility(), indent=2))
