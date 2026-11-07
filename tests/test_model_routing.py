"""Tests for isolated in-process model routing."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.model_orchestrator.routing import ModelRouter


ENDPOINT = "http://127.0.0.1:42516/v1"


def make_router():
    return ModelRouter(ENDPOINT, "unicron-qwen")


def test_initial_route():
    route = make_router().snapshot()
    assert route.model == "unicron-qwen"
    assert route.generation == 0


def test_switch():
    router = make_router()
    route = router.switch("http://127.0.0.1:42517/v1", "candidate")
    assert route.model == "candidate"
    assert route.generation == 1


def test_rollback():
    router = make_router()
    router.switch("http://127.0.0.1:42517/v1", "candidate")
    restored = router.rollback()
    assert restored.model == "unicron-qwen"
    assert restored.generation == 2


def test_rollback_without_previous_route():
    with pytest.raises(RuntimeError):
        make_router().rollback()


def test_invalid_endpoint_rejected():
    router = make_router()
    with pytest.raises(ValueError):
        router.switch("https://example.com/v1", "candidate")
    assert router.snapshot().model == "unicron-qwen"


def test_empty_model_rejected():
    router = make_router()
    with pytest.raises(ValueError):
        router.switch(ENDPOINT, "")
    assert router.snapshot().generation == 0


def test_noop_switch():
    router = make_router()
    route = router.switch(ENDPOINT, "unicron-qwen")
    assert route.generation == 0


def test_snapshot_is_immutable():
    router = make_router()
    before = router.snapshot()
    router.switch("http://127.0.0.1:42517/v1", "candidate")
    assert before.model == "unicron-qwen"
    assert before.generation == 0


def test_concurrent_snapshots_and_switches():
    router = make_router()

    def operation(index):
        if index % 2:
            return router.switch(
                "http://127.0.0.1:42517/v1",
                "candidate",
            )
        return router.snapshot()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(operation, range(100)))

    assert len(results) == 100
    assert all(result.generation >= 0 for result in results)
    assert router.snapshot().model in ("unicron-qwen", "candidate")
