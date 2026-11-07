"""Create in-memory or persistent model routers."""

from __future__ import annotations

import os
from pathlib import Path



def create_router(
    endpoint: str,
    model: str,
    *,
    persistent: bool | None = None,
    db_path: str | Path | None = None,
):
    if persistent is None:
        persistent = (
            os.getenv("CIVITAS_MODEL_ROUTING_PERSISTENT", "0") == "1"
        )

    if not persistent:
        from .routing import ModelRouter

        return ModelRouter(endpoint, model)

    if db_path is None:
        configured = os.getenv("CIVITAS_MODEL_ROUTING_DB", "").strip()
        db_path = (
            Path(configured)
            if configured
            else Path(__file__).resolve().parents[3]
            / "data"
            / "model_routes.sqlite3"
        )

    from .durable_router import DurableModelRouter

    return DurableModelRouter(db_path, endpoint, model)
