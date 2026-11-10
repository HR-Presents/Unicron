# UNICRON

**Unified Network for Intelligence, Compliance, Research, Oversight and Navigation**

An autonomous AI intelligence system for evidence-grounded investigation, regulatory analysis, and cross-jurisdictional policy intelligence.

## Workspace

The application is a minimal conversational workspace: describe a case, receive recorded six-agent findings with evidence references, and ask follow-up questions. It includes matte black and porcelain themes, a geometric SVG U identity, investigation search/history and a compact expandable execution panel. The previous Command Center, 3D twin, manual Scenario Lab and dashboard frontend have been removed.

The existing FastAPI/SQLite backend, durable worker, PDF processing, evidence retrieval, source provenance, citation validation and Qwen orchestration remain. Investigations complete advisory synthesis without a human approval step. Unsupported claims, absent sources, uncertain legal applicability and hypothetical scenarios remain explicit. Advisory completion does not mean evidence was verified or a policy decision was approved. Legacy provenance and review endpoints remain available for compatibility; the workspace does not require review actions.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
```

Start Qwen/llama.cpp/vLLM separately with an OpenAI-compatible chat-completions endpoint. Export `CIVITAS_LLM_BASE_URL`, the server's actual `CIVITAS_LLM_MODEL`, and optionally `CIVITAS_LLM_API_KEY`. Set `CIVITAS_DB_PATH` to your existing database if needed. See [backend/.env.example](backend/.env.example); examples are not automatically loaded.

```bash
./start.sh
```

This starts the API, queue worker and conversational frontend. It does not install or start Qwen. API/model credentials stay server-side.

## Connect the private hosted workspace

The hosted Site cannot reach your laptop's `127.0.0.1` address. Use a hosted API or authenticated HTTPS tunnel to the running API. Keep Qwen private and configure the Site runtime with:

- `UNICRON_API_URL`: API origin, without `/api` at the end.
- `UNICRON_API_TOKEN`: the same secret as the backend's `CIVITAS_API_KEY`.
- `UNICRON_MODEL_VIA_BACKEND=1`: route follow-up generation through the API's configured Qwen service.

The API and queue worker must use the same database, model settings, and credentials. Avoid committing databases, PDFs, model weights or tokens. Read-only connection check:

```bash
.venv/bin/python scripts/check-connections.py
```

A reachable API is not proof that Qwen generation or the worker works. Production verification still requires a real queued investigation, six recorded stages, persisted cited output, and a follow-up response. No endpoint URL, credentials or local November 10 backend files were available in the remote development workspace; those have not been silently reconciled or connected.

## Build and test

```bash
npm run build
npm test
.venv/bin/python -m pytest -q
```

The build produces the React client and existing authenticated Worker gateway at `dist/server/index.js`. The API, worker, database and model are hosted separately.
