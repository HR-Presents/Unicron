# Reconciled UNICRON workspace

The premium React conversational interface is combined with laptop backend commit `866f119` and all its committed research/model-orchestrator work. The superseded dashboard, 3D twin and manual navigation panels remain removed.

Preserved: shared verified evidence retrieval; discovery/import and PDF worker limits; source grounding and provenance; global investigation locking and queues; standards traceability in backend results; durable/pinned model routing; case deletion API; structured, retried follow-ups; conversation context; general chat and automatic investigation classification. No regulatory PDFs, runtime databases, model files, local logs or backup files are committed.

The gateway uses `/api/model/completion` through the authenticated API when `UNICRON_MODEL_VIA_BACKEND=1`. All three inference flows—routing, general chat and cited case follow-up—use the backend's current model router. Qwen stays on its existing private loopback endpoint. The narrower `/api/model/briefing` route remains compatible. Generated thought content and model endpoint details are not exposed through the gateway.

Advisory reports and checkpoint serialization complete without a mandatory human approval step. Evidence provenance, citation validation, source eligibility and uncertainty are preserved. Source verification metadata is never promoted to verified merely to enable automation. Existing optional legacy review APIs remain for compatibility.

Validation: 476 Python tests plus 2 subtests, 14 frontend/gateway tests, and the production client/Worker build pass. Run Python tests using `PYTHONPATH=.:backend .venv/bin/python -m pytest -q tests backend/tests`; subprocess tests inherit that import path.

Still required: an authenticated HTTPS connection to the running laptop API, a running worker using the existing database, and real Qwen investigation/follow-up validation. The cloud workspace has no access to the laptop's runtime state or local PDFs. The user's remaining untracked chat frontend/backups are untouched; the premium UI does not depend on that old chat folder.
