"""Safety tests for in-memory process ownership."""

import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.model_orchestrator.process_manager import (
    ProcessManager,
)


def sleeping_command():
    return [
        sys.executable,
        "-c",
        "import time; time.sleep(30)",
    ]


def test_start_requires_approval():
    manager = ProcessManager()

    with pytest.raises(PermissionError):
        manager.start(sleeping_command())


def test_stop_requires_approval():
    manager = ProcessManager()
    child = manager.start(sleeping_command(), approved=True)

    try:
        with pytest.raises(PermissionError):
            manager.stop(child.pid)

        assert manager.status(child.pid)["running"]
    finally:
        manager.stop(child.pid, approved=True)


def test_unmanaged_pid_rejected():
    manager = ProcessManager()

    with pytest.raises(ValueError):
        manager.stop(999999, approved=True)


@pytest.mark.parametrize(
    "command",
    [[], [""] , ["python", None], "python"],
)
def test_invalid_command_rejected(command):
    manager = ProcessManager()

    with pytest.raises(ValueError):
        manager.start(command, approved=True)


def test_owned_child_lifecycle():
    manager = ProcessManager()
    child = manager.start(sleeping_command(), approved=True)

    try:
        assert manager.status(child.pid)["managed"]
        assert manager.status(child.pid)["running"]
    finally:
        result = manager.stop(child.pid, approved=True)

    assert result["managed"]
    assert not result["running"]


def test_repeated_stop_is_safe():
    manager = ProcessManager()
    child = manager.start(sleeping_command(), approved=True)

    first = manager.stop(child.pid, approved=True)
    second = manager.stop(child.pid, approved=True)

    assert not first["running"]
    assert not second["running"]


def test_separate_managers_cannot_stop_each_others_children():
    first = ProcessManager()
    second = ProcessManager()

    child = first.start(sleeping_command(), approved=True)

    try:
        with pytest.raises(ValueError):
            second.stop(child.pid, approved=True)

        assert first.status(child.pid)["running"]
    finally:
        first.stop(child.pid, approved=True)


def test_concurrent_status_reads():
    manager = ProcessManager()
    child = manager.start(sleeping_command(), approved=True)

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    manager.status,
                    [child.pid] * 32,
                )
            )

        assert len(results) == 32
        assert all(item["managed"] for item in results)
        assert all(item["running"] for item in results)
    finally:
        manager.stop(child.pid, approved=True)
