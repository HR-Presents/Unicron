"""Tests for context-local model route pinning."""

from concurrent.futures import ThreadPoolExecutor

from backend.app.model_orchestrator.pinning import (
    current_route,
    pin_route,
)
from backend.app.model_orchestrator.routing import ModelRoute


ROUTE_A = ModelRoute("http://127.0.0.1:42516/v1", "model-a", 1)
ROUTE_B = ModelRoute("http://127.0.0.1:42517/v1", "model-b", 2)


def test_explicit_pin():
    with pin_route(ROUTE_A):
        assert current_route() == ROUTE_A


def test_nested_pin_restores_parent():
    with pin_route(ROUTE_A):
        with pin_route(ROUTE_B):
            assert current_route() == ROUTE_B
        assert current_route() == ROUTE_A


def test_pin_resets_after_exception():
    try:
        with pin_route(ROUTE_A):
            raise RuntimeError("test")
    except RuntimeError:
        pass
    assert current_route() != ROUTE_A


def test_threads_have_independent_pins():
    def worker(route):
        with pin_route(route):
            return current_route()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, [ROUTE_A, ROUTE_B]))

    assert results == [ROUTE_A, ROUTE_B]
