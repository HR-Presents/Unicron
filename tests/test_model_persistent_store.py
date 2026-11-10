"""Tests for durable, generation-checked model routing."""

import pytest

from backend.app.model_orchestrator.persistent_store import (
    PersistentRouteStore,
    RouteConflict,
)


ENDPOINT = "http://127.0.0.1:42516/v1"


def test_initialize_and_snapshot(tmp_path):
    store = PersistentRouteStore(tmp_path / "routes.sqlite3")
    route = store.initialize(ENDPOINT, "model-a")

    assert route.model == "model-a"
    assert route.generation == 0
    assert store.snapshot() == route


def test_persists_across_instances(tmp_path):
    path = tmp_path / "routes.sqlite3"
    first = PersistentRouteStore(path)
    first.initialize(ENDPOINT, "model-a")
    first.switch(ENDPOINT, "model-b", expected_generation=0)

    second = PersistentRouteStore(path)
    route = second.initialize(ENDPOINT, "model-a")

    assert route.model == "model-b"
    assert route.generation == 1


def test_rejects_stale_generation(tmp_path):
    path = tmp_path / "routes.sqlite3"
    first = PersistentRouteStore(path)
    second = PersistentRouteStore(path)

    first.initialize(ENDPOINT, "model-a")
    first.switch(ENDPOINT, "model-b", expected_generation=0)

    with pytest.raises(RouteConflict):
        second.switch(
            ENDPOINT, "model-c",
            expected_generation=0,
        )

    assert first.snapshot().model == "model-b"


def test_noop_preserves_generation(tmp_path):
    store = PersistentRouteStore(tmp_path / "routes.sqlite3")
    store.initialize(ENDPOINT, "model-a")

    route = store.switch(
        ENDPOINT, "model-a",
        expected_generation=0,
    )

    assert route.generation == 0


def test_rollback_restores_previous_model(tmp_path):
    store = PersistentRouteStore(tmp_path / "routes.sqlite3")
    store.initialize(ENDPOINT, "model-a")

    store.switch(ENDPOINT, "model-b", expected_generation=0)

    restored = store.rollback(expected_generation=1)

    assert restored.model == "model-a"
    assert restored.generation == 2


def test_rollback_without_history_fails(tmp_path):
    store = PersistentRouteStore(tmp_path / "routes.sqlite3")
    store.initialize(ENDPOINT, "model-a")

    with pytest.raises(RuntimeError, match="No previous route"):
        store.rollback(expected_generation=0)


def test_invalid_endpoint_rejected(tmp_path):
    store = PersistentRouteStore(tmp_path / "routes.sqlite3")
    store.initialize(ENDPOINT, "model-a")

    with pytest.raises(ValueError):
        store.switch(
            "https://example.com/v1",
            "model-b",
            expected_generation=0,
        )

    assert store.snapshot().model == "model-a"
