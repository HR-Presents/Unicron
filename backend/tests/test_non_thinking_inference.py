"""Regression tests for Qwen3 non-thinking backend inference payloads."""
import io
import json

from backend.app import investigation, triage


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_triage_requests_non_thinking_json(monkeypatch):
    captured = {}

    def fake_open(request, timeout):
        captured.update(json.loads(request.data))
        return FakeResponse(json.dumps({
            "model": "unicron-local",
            "choices": [{"message": {"content": json.dumps({
                "classification": "Healthcare",
                "recommended_priority": "Medium",
                "rationale": "Requires a qualified human review.",
                "missing_evidence": [],
                "immediate_actions": [],
            })}}]
        }).encode())

    class FakeOpener:
        def open(self, request, timeout):
            return fake_open(request, timeout)

    monkeypatch.setattr(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        lambda *args: FakeOpener(),
    )
    result, model = triage.infer({
        "title": "Healthcare case",
        "summary": "Assess healthcare AI governance.",
        "domain": "Healthcare",
        "priority": "Medium",
    })
    assert captured["chat_template_kwargs"]["enable_thinking"] is False
    assert captured["stream"] is False
    assert result["classification"] == "Healthcare"
    assert model == "unicron-local"


def test_investigation_requests_non_thinking_json(monkeypatch):
    captured = {}

    def fake_open(request, timeout):
        captured.update(json.loads(request.data))
        return FakeResponse(b'{"choices":[{"message":{"content":"{\\\"ok\\\": true}"}}]}')

    class FakeInvestigationOpener:
        def open(self, request, timeout):
            return fake_open(request, timeout)

    monkeypatch.setattr(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        lambda *args: FakeInvestigationOpener(),
    )
    result = investigation.model_json("Test system", {"topic": "health"}, '{"ok":boolean}', max_tokens=30)
    assert result == {"ok": True}
    assert captured["chat_template_kwargs"]["enable_thinking"] is False
    assert captured["max_tokens"] == 30
