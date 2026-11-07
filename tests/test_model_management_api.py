"""Security tests for model management API."""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.model_orchestrator.api import install


ENDPOINT = "http://127.0.0.1:42516/v1"


def make_client():
    app = FastAPI()
    install(app)
    return TestClient(app)


def payload(approved=True):
    return {
        "endpoint": ENDPOINT,
        "model": "test-model",
        "approved": approved,
    }


def test_activation_disabled_without_admin_token(monkeypatch):
    monkeypatch.delenv("CIVITAS_MODEL_ADMIN_TOKEN", raising=False)
    client = make_client()

    response = client.post(
        "/api/models/activate",
        json=payload(),
    )

    assert response.status_code == 503


def test_activation_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("CIVITAS_MODEL_ADMIN_TOKEN", "test-secret")
    client = make_client()

    response = client.post(
        "/api/models/activate",
        json=payload(),
    )

    assert response.status_code == 403


def test_activation_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("CIVITAS_MODEL_ADMIN_TOKEN", "test-secret")
    client = make_client()

    response = client.post(
        "/api/models/activate",
        json=payload(),
        headers={"X-Model-Admin-Token": "wrong-secret"},
    )

    assert response.status_code == 403


def test_activation_requires_explicit_approval(monkeypatch):
    monkeypatch.setenv("CIVITAS_MODEL_ADMIN_TOKEN", "test-secret")
    client = make_client()

    response = client.post(
        "/api/models/activate",
        json=payload(approved=False),
        headers={"X-Model-Admin-Token": "test-secret"},
    )

    assert response.status_code == 400


def test_authorized_activation_uses_controller(monkeypatch):
    monkeypatch.setenv("CIVITAS_MODEL_ADMIN_TOKEN", "test-secret")
    client = make_client()

    with patch(
        "backend.app.model_orchestrator.api.activate_model",
        return_value={
            "activated": True,
            "model": "test-model",
            "generation": 1,
        },
    ) as mocked:
        response = client.post(
            "/api/models/activate",
            json=payload(),
            headers={"X-Model-Admin-Token": "test-secret"},
        )

    assert response.status_code == 200
    assert response.json()["activated"] is True
    mocked.assert_called_once_with(
        endpoint=ENDPOINT,
        model="test-model",
        approved=True,
    )


def test_status_does_not_expose_endpoint(monkeypatch):
    monkeypatch.delenv("CIVITAS_MODEL_ADMIN_TOKEN", raising=False)
    client = make_client()

    response = client.get("/api/models/status")

    assert response.status_code == 200
    assert "endpoint" not in response.json()
    assert "model" in response.json()
