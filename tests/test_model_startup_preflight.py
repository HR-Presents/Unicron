"""Safety tests for local vLLM startup preflight."""

from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from backend.app.model_orchestrator.startup_preflight import (
    gpu_memory_mib,
    port_available,
    startup_preflight,
)


MODEL = "Qwen/Qwen3-1.7B"
MODULE = "backend.app.model_orchestrator.startup_preflight"


@pytest.fixture
def snapshot(tmp_path):
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / "config.json").write_text("{}")
    (root / "tokenizer_config.json").write_text("{}")
    (root / "model.safetensors").write_bytes(b"test")
    return root


@pytest.fixture
def executable(tmp_path):
    path = tmp_path / "vllm"
    path.write_text("#!/bin/sh\\n")
    path.chmod(0o755)
    return path


def check(snapshot, executable, free, port=True):
    with patch(
        MODULE + ".gpu_memory_mib",
        return_value={
            "total": 16384,
            "used": 16384 - free,
            "free": free,
        },
    ), patch(
        MODULE + ".port_available",
        return_value=port,
    ):
        return startup_preflight(
            MODEL,
            snapshot,
            runtime_executable=executable,
        )


def test_insufficient_gpu(snapshot, executable):
    result = check(snapshot, executable, 976)
    assert not result["ready"]
    assert not result["checks"]["gpu_memory_sufficient"]


def test_sufficient_gpu(snapshot, executable):
    result = check(snapshot, executable, 15360)
    assert result["ready"]
    assert not result["started"]
    assert not result["activated"]


def test_busy_port(snapshot, executable):
    result = check(snapshot, executable, 15360, port=False)
    assert not result["ready"]
    assert not result["checks"]["port_available"]


def test_missing_runtime(snapshot, tmp_path):
    result = check(snapshot, tmp_path / "missing", 15360)
    assert not result["ready"]
    assert not result["checks"]["runtime_executable"]


def test_unapproved_model(snapshot, executable):
    with pytest.raises(ValueError):
        startup_preflight(
            "unknown/model",
            snapshot,
            runtime_executable=executable,
        )


def test_invalid_ports():
    for port in (0, 80, 65536, True):
        with pytest.raises(ValueError):
            port_available(port)


def test_multiple_gpus_rejected():
    with patch(
        MODULE + ".subprocess.run",
        return_value=CompletedProcess(
            args=[],
            returncode=0,
            stdout="8188, 1000, 7188\n8188, 1000, 7188\n",
            stderr="",
        ),
    ):
        with pytest.raises(RuntimeError):
            gpu_memory_mib()
