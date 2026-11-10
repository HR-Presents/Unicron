"""Verify resource limits without modifying the pytest process."""

import subprocess
import sys

from app.research_worker import MAX_WORKER_OUTPUT_BYTES


def test_child_resource_limit_in_separate_process():
    """A separate process can lower its hard limit safely."""

    script = """
import resource
import sys

from app.research_worker import MAX_WORKER_OUTPUT_BYTES

resource.setrlimit(
    resource.RLIMIT_FSIZE,
    (MAX_WORKER_OUTPUT_BYTES, MAX_WORKER_OUTPUT_BYTES),
)

soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)

assert soft == MAX_WORKER_OUTPUT_BYTES
assert hard == MAX_WORKER_OUTPUT_BYTES

print("CHILD_LIMIT_OK")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "CHILD_LIMIT_OK" in result.stdout


def test_parent_resource_limit_unchanged():
    """The test runner must retain its original limits."""
    import resource

    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)

    assert hard == resource.RLIM_INFINITY or hard > MAX_WORKER_OUTPUT_BYTES
