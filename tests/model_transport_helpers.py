"""Test-only HTTP transport helpers for the model orchestrator."""

import io
import json
from unittest.mock import patch


class FakeOpener:
    def __init__(self, response=None, error=None, capture=None):
        self.response = response
        self.error = error
        self.capture = capture

    def open(self, request, timeout):
        if self.capture is not None:
            self.capture.append(
                (json.loads(request.data.decode("utf-8")), timeout)
            )

        if self.error is not None:
            raise self.error

        return io.BytesIO(json.dumps(self.response).encode("utf-8"))


def mock_model_transport(response=None, error=None, capture=None):
    """Patch only the hardened client's HTTP opener factory."""

    return patch(
        "backend.app.model_orchestrator.client.urllib.request.build_opener",
        return_value=FakeOpener(
            response=response,
            error=error,
            capture=capture,
        ),
    )
