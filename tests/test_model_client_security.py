"""Security and request-integrity tests for the shared model client."""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from backend.app.model_orchestrator.client import completion
from backend.app.model_orchestrator.routing import ModelRoute


ROUTE = ModelRoute(
    "http://127.0.0.1:42516/v1",
    "unicron-qwen",
    0,
)


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        if self.error is not None:
            raise self.error
        return io.BytesIO(json.dumps(self.response).encode())


def test_model_cannot_be_overridden_by_payload():
    opener = FakeOpener({"choices": []})
    with patch(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        return_value=opener,
    ):
        completion({"model": "untrusted", "messages": []}, route=ROUTE)

    payload = json.loads(opener.request.data)
    assert payload["model"] == "unicron-qwen"


def test_non_thinking_configuration_preserved():
    opener = FakeOpener({"choices": []})
    with patch(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        return_value=opener,
    ):
        completion({
            "messages": [],
            "chat_template_kwargs": {"enable_thinking": False},
            "stream": False,
        }, route=ROUTE)

    payload = json.loads(opener.request.data)
    assert payload["chat_template_kwargs"]["enable_thinking"] is False
    assert payload["stream"] is False
    assert opener.timeout == 120


def test_network_failure_propagates_for_agent_handling():
    opener = FakeOpener(error=urllib.error.URLError("private-detail"))
    with patch(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        return_value=opener,
    ):
        with pytest.raises(urllib.error.URLError):
            completion({"messages": []}, route=ROUTE)


def test_external_endpoint_rejected():
    route = ModelRoute("https://example.com/v1", "test", 0)
    with pytest.raises(ValueError):
        completion({"messages": []}, route=route)


def test_payload_not_mutated():
    original = {"model": "original", "messages": []}
    opener = FakeOpener({"choices": []})
    with patch(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        return_value=opener,
    ):
        completion(original, route=ROUTE)

    assert original["model"] == "original"
