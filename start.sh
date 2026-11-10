#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"
VITE="$ROOT/frontend/node_modules/.bin/vite"
if [ ! -x "$PYTHON" ]; then
  echo "Python virtual environment missing. See the local development instructions in README.md."
  exit 1
fi
if [ ! -x "$VITE" ]; then
  echo "Frontend dependencies missing. Run npm ci --prefix frontend."
  exit 1
fi

find_free_port() {
  "$PYTHON" - <<'PY'
import socket
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
}

BACKEND_PORT=$(find_free_port)
FRONTEND_PORT=$(find_free_port)
while [ "$FRONTEND_PORT" = "$BACKEND_PORT" ]; do
  FRONTEND_PORT=$(find_free_port)
done

pids=()
cleanup() {
  kill "${pids[@]}" 2>/dev/null || true
  wait "${pids[@]}" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

"$PYTHON" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
pids+=("$!")

"$PYTHON" - "$BACKEND_PORT" <<'PY'
import sys
import time
from urllib.request import urlopen

url = f"http://127.0.0.1:{sys.argv[1]}/api/health"
deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    try:
        with urlopen(url, timeout=1):
            break
    except OSError:
        time.sleep(0.2)
else:
    raise SystemExit("The UNICRON API did not become ready.")
PY

"$PYTHON" -m backend.app.job_queue &
pids+=("$!")

(
  cd "$ROOT/frontend"
  export UNICRON_MODEL_VIA_BACKEND="${UNICRON_MODEL_VIA_BACKEND:-1}"
  export UNICRON_API_URL="http://127.0.0.1:$BACKEND_PORT"
  if [ -n "${CIVITAS_API_KEY:-}" ] && [ -z "${UNICRON_API_TOKEN:-}" ]; then
    export UNICRON_API_TOKEN="$CIVITAS_API_KEY"
  fi
  exec "$VITE" --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
) &
pids+=("$!")

echo "UNICRON Intelligence Workspace: http://127.0.0.1:$FRONTEND_PORT"
echo "Backend API docs: http://127.0.0.1:$BACKEND_PORT/docs"
echo "Press Ctrl+C to stop the API, worker, and frontend."

wait -n "${pids[@]}"
