"""SQLite-backed model route state with atomic generation updates."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .route_types import ModelRoute
from .runtime import validate_endpoint


class RouteConflict(RuntimeError):
    """Another process updated the model route first."""


class PersistentRouteStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS model_route_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    endpoint TEXT NOT NULL,
                    model TEXT NOT NULL,
                    generation INTEGER NOT NULL
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS model_route_history (
                    generation INTEGER PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    model TEXT NOT NULL
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def initialize(self, endpoint: str, model: str) -> ModelRoute:
        endpoint = validate_endpoint(endpoint)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model name required")

        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO model_route_state
                (id, endpoint, model, generation)
                VALUES (1, ?, ?, 0)
                """,
                (endpoint, model),
            )

        return self.snapshot()

    def snapshot(self) -> ModelRoute:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT endpoint, model, generation
                FROM model_route_state WHERE id = 1
                """
            ).fetchone()

        if row is None:
            raise RuntimeError("Persistent model route not initialized")

        return ModelRoute(*row)

    def switch(
        self,
        endpoint: str,
        model: str,
        *,
        expected_generation: int,
    ) -> ModelRoute:
        endpoint = validate_endpoint(endpoint)
        if not isinstance(model, str) or not model.strip():
            raise ValueError("Model name required")

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")

            row = db.execute(
                """
                SELECT endpoint, model, generation
                FROM model_route_state WHERE id = 1
                """
            ).fetchone()

            if row is None:
                raise RuntimeError("Persistent model route not initialized")

            previous = ModelRoute(*row)

            if previous.generation != expected_generation:
                raise RouteConflict("Model route generation changed")

            if previous.endpoint == endpoint and previous.model == model:
                return previous

            db.execute(
                """
                INSERT INTO model_route_history
                (generation, endpoint, model)
                VALUES (?, ?, ?)
                """,
                (
                    previous.generation,
                    previous.endpoint,
                    previous.model,
                ),
            )

            db.execute(
                """
                UPDATE model_route_state
                SET endpoint = ?, model = ?, generation = ?
                WHERE id = 1
                """,
                (
                    endpoint,
                    model,
                    previous.generation + 1,
                ),
            )
            committed = ModelRoute(
                endpoint, model, previous.generation + 1
            )

        return committed

    def rollback(self, *, expected_generation: int) -> ModelRoute:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")

            current_row = db.execute(
                """
                SELECT endpoint, model, generation
                FROM model_route_state WHERE id = 1
                """
            ).fetchone()

            if current_row is None:
                raise RuntimeError("Persistent model route not initialized")

            current = ModelRoute(*current_row)

            if current.generation != expected_generation:
                raise RouteConflict("Model route generation changed")

            previous_row = db.execute(
                """
                SELECT endpoint, model
                FROM model_route_history
                WHERE generation < ?
                ORDER BY generation DESC LIMIT 1
                """,
                (current.generation,),
            ).fetchone()

            if previous_row is None:
                raise RuntimeError("No previous route available")

            db.execute(
                """
                INSERT INTO model_route_history
                (generation, endpoint, model)
                VALUES (?, ?, ?)
                """,
                (
                    current.generation,
                    current.endpoint,
                    current.model,
                ),
            )

            db.execute(
                """
                UPDATE model_route_state
                SET endpoint = ?, model = ?, generation = ?
                WHERE id = 1
                """,
                (
                    previous_row[0],
                    previous_row[1],
                    current.generation + 1,
                ),
            )
            committed = ModelRoute(
                previous_row[0],
                previous_row[1],
                current.generation + 1,
            )

        return committed
