# Current interface and integration handoff

The source-of-truth branch is `development`. UNICRON uses a conversational centre column, quiet investigation navigation and six explained agent cards opened on demand. The fixed right agent sidebar, 3D dashboard and recursive raw JSON response rendering are removed.

All six independent recorded responses are available in the conversation and agent cards. A selected-agent follow-up uses its matching backend role. Synthesis is presented as prose, findings, next steps, uncertainty and exact source references. Internal reviewer owners/status objects and empty mappings are not dumped into the conversation. Unproven claims remain explicitly limited; source flags and provenance are not rewritten to create the appearance of verification.

Shared archive lookup follows `CIVITAS_EVIDENCE_ARCHIVE_PATH`, or `civitas.sqlite3` beside `CIVITAS_DB_PATH`, independently of the worktree. Exact verified citation lookup is read-only and respects revoked/unverified records. Synthesis now receives bounded policy excerpts and only supported, unflagged comparison context instead of just policy/benchmark status names.

The private frontend still requires a reachable authenticated API. The Qwen service stays local behind `/api/model/completion`. The user's existing database, archive, model process and credentials must remain intact during updates. `scripts/restart-local.py` restarts only an idle matching local workspace and preserves its running API environment.

See README.md for complete setup and docs/REQUIREMENTS.md for honest ITU capability mapping and remaining external integration/submission work. Local automated tests are separate from live model validation.
