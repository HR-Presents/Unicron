"""Durable router concurrency and route pinning tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from backend.app.model_orchestrator.durable_router import (
    DurableModelRouter,
    RouteConflict,
)
from backend.app.model_orchestrator.pinning import pin_route
from backend.app.model_orchestrator.routing import ModelRoute


ENDPOINT = "http://127.0.0.1:42516/v1"


def test_competing_generation_updates(tmp_path):
    router = DurableModelRouter(
        tmp_path / "routes.sqlite3",
        ENDPOINT,
        "model-a",
    )

    barrier = Barrier(2)

    def compete(model):
        current = router.snapshot()
        barrier.wait(timeout=10)

        try:
            return router.store.switch(
                ENDPOINT,
                model,
                expected_generation=current.generation,
            )
        except RouteConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, ["model-b", "model-c"]))

    assert sum(isinstance(r, ModelRoute) for r in results) == 1
    assert results.count("conflict") == 1
    assert router.snapshot().generation == 1


def test_pinned_route_survives_durable_switch(tmp_path):
    router = DurableModelRouter(
        tmp_path / "routes.sqlite3",
        ENDPOINT,
        "model-a",
    )

    initial = router.snapshot()

    with pin_route(initial) as pinned:
        router.switch(ENDPOINT, "model-b")

        assert pinned.model == "model-a"
        assert router.snapshot().model == "model-b"

    assert router.snapshot().model == "model-b"


def test_rollback_visible_to_other_router(tmp_path):
    path = tmp_path / "routes.sqlite3"

    first = DurableModelRouter(path, ENDPOINT, "model-a")
    second = DurableModelRouter(path, ENDPOINT, "model-a")

    first.switch(ENDPOINT, "model-b")

    assert second.snapshot().model == "model-b"

    second.rollback()

    assert first.snapshot().model == "model-a"
    assert first.snapshot().generation == 2
