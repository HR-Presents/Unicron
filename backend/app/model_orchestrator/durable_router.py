"""Persistent model router with the existing router interface."""

from __future__ import annotations

from pathlib import Path

from .persistent_store import PersistentRouteStore, RouteConflict
from .route_types import ModelRoute


class DurableModelRouter:
    """Coordinate route changes through a shared SQLite database."""

    def __init__(
        self,
        db_path: str | Path,
        endpoint: str,
        model: str,
    ):
        self.store = PersistentRouteStore(db_path)
        self.store.initialize(endpoint, model)

    def snapshot(self) -> ModelRoute:
        return self.store.snapshot()

    def switch(self, endpoint: str, model: str) -> ModelRoute:
        current = self.snapshot()
        return self.store.switch(
            endpoint,
            model,
            expected_generation=current.generation,
        )

    def rollback(self) -> ModelRoute:
        current = self.snapshot()
        return self.store.rollback(
            expected_generation=current.generation,
        )


__all__ = [
    "DurableModelRouter",
    "RouteConflict",
]
