"""Context-local model route pinning."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from .routing import ModelRoute, router


_pinned_route: ContextVar[ModelRoute | None] = ContextVar(
    "unicron_pinned_model_route",
    default=None,
)


def current_route() -> ModelRoute:
    """Return the pinned route, or the latest default route."""
    pinned = _pinned_route.get()
    return pinned if pinned is not None else router.snapshot()


@contextmanager
def pin_route(route: ModelRoute | None = None):
    """Keep one model route fixed throughout a logical operation."""
    selected = route if route is not None else current_route()
    token = _pinned_route.set(selected)
    try:
        yield selected
    finally:
        _pinned_route.reset(token)
