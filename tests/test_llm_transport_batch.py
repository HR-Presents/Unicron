"""LLM transport, parsing, privacy and response-shape regression batch."""
import io
import json
import os
import urllib.error
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fastapi import HTTPException
from backend.app import investigation
from tests.model_transport_helpers import mock_model_transport


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return io.BytesIO(json.dumps(self.payload).encode("utf-8"))

    def __exit__(self, *args):
        return False


class ModelTransportBatchTests(unittest.TestCase):
    def call(self, payload):
        with mock_model_transport(response=payload):
            return investigation.model_json("system", {"topic": "public services"}, "{}")

    def test_valid_json_response(self):
        self.assertEqual(self.call({"choices": [{"message": {"content": '{"status":"ok"}'}}]}), {"status": "ok"})

    def test_json_code_fence_response(self):
        self.assertEqual(self.call({"choices": [{"message": {"content": '```json\n{"status":"ok"}\n```'}}]}), {"status": "ok"})

    def test_thinking_block_is_removed(self):
        self.assertEqual(self.call({"choices": [{"message": {"content": '<think>internal</think>{"status":"ok"}'}}]}), {"status": "ok"})

    def test_missing_choices_fails_closed(self):
        with self.assertRaises(HTTPException) as caught:
            self.call({})
        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn("KeyError", str(caught.exception.detail))

    def test_empty_choices_fails_closed(self):
        with self.assertRaises(HTTPException) as caught:
            self.call({"choices": []})
        self.assertEqual(caught.exception.status_code, 502)

    def test_invalid_json_does_not_echo_source_text(self):
        secret = "PRIVATE_EVIDENCE_DO_NOT_LOG"
        with self.assertRaises(HTTPException) as caught:
            self.call({"choices": [{"message": {"content": secret}}]})
        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn(secret, str(caught.exception.detail))

    def test_network_unavailable_returns_503_without_secret(self):
        with mock_model_transport(error=urllib.error.URLError("PRIVATE_NETWORK_DETAIL")):
            with self.assertRaises(HTTPException) as caught:
                investigation.model_json("system", {}, "{}")
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("PRIVATE_NETWORK_DETAIL", str(caught.exception.detail))

    def test_timeout_returns_503(self):
        with mock_model_transport(error=TimeoutError("secret")):
            with self.assertRaises(HTTPException) as caught:
                investigation.model_json("system", {}, "{}")
        self.assertEqual(caught.exception.status_code, 503)

    def test_request_is_nonstreaming_and_deterministic(self):
        captured = []
        def respond(req, timeout):
            captured.append((json.loads(req.data.decode("utf-8")), timeout))
            return FakeResponse({"choices": [{"message": {"content": "{}"}}]})
        with mock_model_transport(
            response={"choices": [{"message": {"content": "{}"}}]},
            capture=captured,
        ):
            investigation.model_json("system", {}, "{}", max_tokens=125)
        body, timeout = captured[0]
        self.assertEqual(body["temperature"], 0)
        self.assertIs(body["stream"], False)
        self.assertEqual(body["max_tokens"], 125)
        self.assertEqual(timeout, 120)

    def test_timing_disabled_does_not_log_prompts(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"CIVITAS_LLM_TIMING": "0"}):
            with redirect_stdout(output):
                self.call({"choices": [{"message": {"content": "{}"}}]})
        self.assertEqual(output.getvalue(), "")

    def test_timing_enabled_only_logs_metadata(self):
        output = io.StringIO()
        with patch.dict(os.environ, {"CIVITAS_LLM_TIMING": "1"}):
            with redirect_stdout(output):
                with mock_model_transport(response={"choices": [{"message": {"content": "{}"}}]}):
                    investigation.model_json("SECRET_SYSTEM_PROMPT", {"secret": "SECRET_CONTEXT"}, "{}", max_tokens=99)
        value = output.getvalue()
        self.assertIn("elapsed_seconds=", value)
        self.assertIn("max_tokens=99", value)
        self.assertNotIn("SECRET_SYSTEM_PROMPT", value)
        self.assertNotIn("SECRET_CONTEXT", value)


if __name__ == "__main__":
    unittest.main()
