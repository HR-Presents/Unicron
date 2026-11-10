# Interface and integration handoff

The premium conversational frontend replaces the previous dashboard in the original UNICRON source tree. Superseded UI modules, rehearsal tests and Three.js/GSAP dependencies are removed. The existing Python backend and Worker gateway are retained.

Backend advisory reports and checkpoint serialization no longer request human approval to finish. Evidence checks, uncertainty, citation validation and the prohibition on treating generated output as approved policy remain. Existing source verification endpoints are preserved.

Follow-ups can run through the authenticated API relay at `/api/model/briefing`, using the same private Qwen configuration as the six agents. This needs only one reachable HTTPS API, not a public Qwen port. Configure `UNICRON_MODEL_VIA_BACKEND=1` plus `UNICRON_API_URL` and `UNICRON_API_TOKEN` in the private Site runtime.

The laptop's November 10 backend changes and runtime data are not accessible here. The available backend baseline is GitHub `development` at `3a92946db596e64aa52579b961cfd5eb3a6b13f1`; do not overwrite uncommitted laptop work when synchronizing. Push the current local backend on a separate branch for reconciliation. Live inference and a real production investigation remain unverified until the API connection and latest backend are available.

Validation: 146 backend tests plus 2 subtests, 11 active frontend/gateway tests, and production client/Worker build passed. Removed rehearsal-only tests belonged to the removed interface, not live-agent validation.
