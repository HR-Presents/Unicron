"""Tests for approval-gated vLLM launch planning."""

from unittest.mock import patch

import pytest

from backend.app.model_orchestrator.runtime_launcher import (
    plan_runtime_launch,
)


MODEL = "Qwen/Qwen3-1.7B"
MODULE = "backend.app.model_orchestrator.runtime_launcher"


@pytest.fixture
def snapshot(tmp_path):
    path = tmp_path / "snapshot"
    path.mkdir()
    return path


@pytest.fixture
def executable(tmp_path):
    path = tmp_path / "vllm"
    path.write_text("#!/bin/sh\\n")
    path.chmod(0o755)
    return path


def launch(snapshot, executable, *, ready=True, **kwargs):
    with patch(
        MODULE + ".startup_preflight",
        return_value={"ready": ready},
    ):
        return plan_runtime_launch(
            MODEL,
            snapshot,
            served_name="unicron-candidate",
            runtime_executable=executable,
            approved=True,
            **kwargs,
        )


def test_approval_required(snapshot, executable):
    with pytest.raises(PermissionError):
        plan_runtime_launch(
            MODEL,
            snapshot,
            served_name="unicron-candidate",
            runtime_executable=executable,
        )


def test_rejects_unsafe_gpu(snapshot, executable):
    result = launch(snapshot, executable, ready=False)

    assert result["ready"] is False
    assert result["command"] is None
    assert result["started"] is False


def test_safe_command_is_local(snapshot, executable):
    result = launch(snapshot, executable)

    assert result["ready"] is True
    assert result["started"] is False

    command = result["command"]

    assert command[0] == str(executable)
    assert command[1] == "serve"
    assert "--host" in command
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "42517"
    assert command[command.index("--served-model-name") + 1] == (
        "unicron-candidate"
    )


def test_rejects_unapproved_model(snapshot, executable):
    with pytest.raises(ValueError):
        plan_runtime_launch(
            "unknown/model",
            snapshot,
            served_name="unicron-candidate",
            runtime_executable=executable,
            approved=True,
        )


@pytest.mark.parametrize(
    "name",
    ["", "bad name", "model;shutdown", "../model"],
)
def test_rejects_invalid_served_name(snapshot, executable, name):
    with pytest.raises(ValueError):
        plan_runtime_launch(
            MODEL,
            snapshot,
            served_name=name,
            runtime_executable=executable,
            approved=True,
        )


@pytest.mark.parametrize(
    "context",
    [0, 100, 100000, True],
)
def test_rejects_invalid_context(snapshot, executable, context):
    with pytest.raises(ValueError):
        plan_runtime_launch(
            MODEL,
            snapshot,
            served_name="unicron-candidate",
            runtime_executable=executable,
            approved=True,
            max_model_len=context,
        )


@pytest.mark.parametrize(
    "utilization",
    [0, 0.99, -0.5, True],
)
def test_rejects_invalid_utilization(
    snapshot, executable, utilization
):
    with pytest.raises(ValueError):
        plan_runtime_launch(
            MODEL,
            snapshot,
            served_name="unicron-candidate",
            runtime_executable=executable,
            approved=True,
            gpu_memory_utilization=utilization,
        )


def test_custom_port(snapshot, executable):
    result = launch(
        snapshot,
        executable,
        port=42600,
    )

    command = result["command"]
    assert command[command.index("--port") + 1] == "42600"
