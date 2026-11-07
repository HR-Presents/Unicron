"""Isolated tests for guarded model activation."""

from unittest.mock import patch

import pytest

from backend.app.model_orchestrator.activation_controller import activate_model
from backend.app.model_orchestrator.routing import ModelRouter


ENDPOINT = "http://127.0.0.1:42516/v1"


def make_router():
    return ModelRouter(ENDPOINT, "original-model")


def test_approval_required():
    router = make_router()

    with pytest.raises(PermissionError):
        activate_model(
            ENDPOINT, "new-model",
            approved=False, model_router=router,
        )

    assert router.snapshot().model == "original-model"


def test_unavailable_model_does_not_activate():
    router = make_router()

    with patch(
        "backend.app.model_orchestrator.activation_controller.probe_runtime",
        return_value={
            "reachable": True,
            "model_available": False,
            "inference_passed": False,
        },
    ):
        result = activate_model(
            ENDPOINT, "new-model",
            approved=True, model_router=router,
        )

    assert result["activated"] is False
    assert result["reason"] == "runtime_validation_failed"
    assert router.snapshot().model == "original-model"


def test_incompatible_model_does_not_activate():
    router = make_router()

    with (
        patch(
            "backend.app.model_orchestrator.activation_controller.probe_runtime",
            return_value={
                "reachable": True,
                "model_available": True,
                "inference_passed": True,
            },
        ),
        patch(
            "backend.app.model_orchestrator.activation_controller.check_compatibility",
            return_value={"compatible": False},
        ),
    ):
        result = activate_model(
            ENDPOINT, "new-model",
            approved=True, model_router=router,
        )

    assert result["activated"] is False
    assert result["reason"] == "compatibility_validation_failed"
    assert router.snapshot().model == "original-model"


def test_successful_activation_and_rollback():
    router = make_router()

    with (
        patch(
            "backend.app.model_orchestrator.activation_controller.probe_runtime",
            return_value={
                "reachable": True,
                "model_available": True,
                "inference_passed": True,
            },
        ),
        patch(
            "backend.app.model_orchestrator.activation_controller.check_compatibility",
            return_value={"compatible": True},
        ),
    ):
        result = activate_model(
            ENDPOINT, "new-model",
            approved=True, model_router=router,
        )

    assert result["activated"] is True
    assert router.snapshot().model == "new-model"
    assert router.snapshot().generation == 1

    restored = router.rollback()
    assert restored.model == "original-model"
    assert restored.generation == 2
