"""Protected model management endpoints."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from .activation_controller import activate_model
from .routing import router


api = APIRouter(prefix="/api/models", tags=["Model Management"])


class ActivationRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    approved: bool = False


@api.get("/status")
def model_status():
    route = router.snapshot()
    return {
        "model": route.model,
        "generation": route.generation,
        "runtime": "local",
        "activation_configured": bool(
            os.getenv("CIVITAS_MODEL_ADMIN_TOKEN", "").strip()
        ),
    }


@api.post("/activate")
def model_activate(
    payload: ActivationRequest,
    admin_token: str | None = Header(
        default=None,
        alias="X-Model-Admin-Token",
    ),
):
    expected = os.getenv("CIVITAS_MODEL_ADMIN_TOKEN", "").strip()

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Model administration is not configured",
        )

    if (
        not admin_token
        or not hmac.compare_digest(admin_token, expected)
    ):
        raise HTTPException(
            status_code=403,
            detail="Model administrator authorization required",
        )

    if payload.approved is not True:
        raise HTTPException(
            status_code=400,
            detail="Explicit activation approval required",
        )

    try:
        result = activate_model(
            endpoint=payload.endpoint,
            model=payload.model,
            approved=True,
        )
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid local model endpoint or model name",
        )
    except (OSError, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Model activation failed",
        )

    return result


def install(app):
    app.include_router(api)
