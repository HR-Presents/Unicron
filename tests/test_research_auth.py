"""Regression tests for fail-closed research authentication."""

import os
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.research_auth import require_research_auth


def test_missing_configuration_disables_research_import():
    with patch.dict(os.environ, {"CIVITAS_API_KEY": ""}):
        with pytest.raises(HTTPException) as exc:
            require_research_auth("Bearer anything")

    assert exc.value.status_code == 503


def test_missing_token_rejected():
    with patch.dict(os.environ, {"CIVITAS_API_KEY": "secret"}):
        with pytest.raises(HTTPException) as exc:
            require_research_auth(None)

    assert exc.value.status_code == 401


def test_wrong_token_rejected():
    with patch.dict(os.environ, {"CIVITAS_API_KEY": "secret"}):
        with pytest.raises(HTTPException) as exc:
            require_research_auth("Bearer incorrect")

    assert exc.value.status_code == 401


def test_wrong_authentication_scheme_rejected():
    with patch.dict(os.environ, {"CIVITAS_API_KEY": "secret"}):
        with pytest.raises(HTTPException) as exc:
            require_research_auth("Basic secret")

    assert exc.value.status_code == 401


def test_valid_token_accepted():
    with patch.dict(os.environ, {"CIVITAS_API_KEY": "secret"}):
        assert require_research_auth("Bearer secret") is None
