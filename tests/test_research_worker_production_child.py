"""Verify the real child entry point in a separate process."""

import subprocess
import sys

from app.research_worker import MAX_WORKER_OUTPUT_BYTES


def test_production_child_sets_limit_before_retrieval():
    script = r'''
import io
import resource
import sys

from app import research_retrieval, research_worker

expected = research_worker.MAX_WORKER_OUTPUT_BYTES

def controlled_download(url):
    assert url == "https://policy.example/document"
    assert resource.getrlimit(resource.RLIMIT_FSIZE) == (
        expected,
        expected,
    )
    print("PRODUCTION_CHILD_LIMIT_OK", file=sys.stderr)
    raise RuntimeError("STOP_BEFORE_NETWORK")

research_retrieval._download_https_document = controlled_download

class FakeStdin:
    buffer = io.BytesIO(b"https://policy.example/document")

sys.stdin = FakeStdin()

try:
    research_worker._worker_main()
except RuntimeError as exc:
    if str(exc) != "STOP_BEFORE_NETWORK":
        raise
else:
    raise AssertionError("Controlled downloader was not invoked")
'''

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "PRODUCTION_CHILD_LIMIT_OK" in result.stderr


def test_parent_process_limit_is_not_modified():
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)

    assert hard == resource.RLIM_INFINITY or (
        hard > MAX_WORKER_OUTPUT_BYTES
    )
