"""Fail-closed authentication for network-enabled research operations."""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_research_auth(
    authorization: str | None = Header(default=None),
) -> None:
    """Require the deployment API key for research import operations.

    Unlike the optional global middleware, this dependency rejects
    requests when the deployment key is not configured.
    """

    expected = os.getenv("CIVITAS_API_KEY", "").strip()

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Research import disabled: configure CIVITAS_API_KEY",
        )

    prefix = "Bearer "

    if (
        not authorization
        or not authorization.startswith(prefix)
        or not hmac.compare_digest(
            authorization[len(prefix):],
            expected,
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Research import authentication required",
        )
