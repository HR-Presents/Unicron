# ITU AI for Good UAE requirements mapping

Source: [Official hackathon brief](https://aiforgood.itu.int/event/ai-for-good-sandbox-hackathon-united-arab-emirates/), checked 10 November 2026. The brief prioritizes domain-specific policy gaps and relevant global examples. A feature being implemented does not establish legal compliance or ITU certification.

| Requirement | Implementation and evidence | Current boundary |
| --- | --- | --- |
| Domain-specific agent solution | Case creation, six persisted agent stages, scenario evaluator; `backend/app/investigation.py` | Quality depends on the case, model and available documentary evidence |
| National knowledge and global policy examples | Provenance-backed policy/benchmark retrieval, legal-scope and citation checks; `evidence.py`, `policy_intelligence.py`, `grounded_policy.py` | New clones contain no regulatory PDFs or pre-verified national corpus |
| Shared country knowledge base | SQLite documentary archive and moderated community contributions; `knowledge_base.py` | Community context is not official documentary evidence |
| ITU reference extraction/ingestion | Read-only JSONL/manifest export through `scripts/export-knowledge.py`; official reference: [ITUAIReadiness](https://github.com/CrashingGuru/ITUAIReadiness) | The current retrieval engine is lexical/ranked SQLite retrieval. Distributed vector indexing and ingestion into the ITU Lab are not implemented or deployed here |
| Sandbox model work | Configurable local Qwen transport, durable model routing and vLLM launch/preflight helpers | Sandbox access/credits and fine-tuning have not been performed by this repository |
| Policy/legal adviser and coordination | Policy Advisor, Global Benchmark Agent and functional six-agent coordination | Functional agent roles are not a claim that ministries or regulators have endorsed the system |
| Progressively released error scenarios | Durable scenario sessions; `start`, `next`, `evaluate-next`, `pause`, `resume`; `scenario_sessions.py` | Scenario APIs remain available without a manual Scenario Lab tab. Main chat investigations are not themselves the staged-session scheduler |
| Auditability and policy references | Ordered execution events, persisted agent outputs, source IDs, audit entries and explicit uncertainty | Expose concise decision rationales and source attribution; private model chain-of-thought is not published |
| ITU-T Y.3172 alignment | Data intake → processing/retrieval → model analysis → recorded outputs; source and model management modules | An architectural mapping, not a conformity assessment or certification |
| AI Readiness Framework 2.0 | Provenance/open-data boundaries, domain context, model/compute setup, interactive inspection, policy-gap analysis; standards traceability API | Explicit evidence-backed framework mappings must be populated and assessed for each case; empty mappings are not compliant findings |
| Human interaction/supervision | Conversational follow-ups, agent inspection, source references and optional authenticated provenance/review APIs | Normal advisory investigations do not wait for human approval. The system does not execute government decisions |
| Submission | This GitHub repository, installation guide, demo workflow and requirements mapping | A five-page technical report, licensed knowledge-base contribution and any required demo video remain separate submission deliverables |

## Demonstrating the staged scenario requirement

The JSON at `docs/examples/healthcare-scenario.json` is explicitly synthetic. Create a case, then POST that JSON to `/api/cases/{case_id}/scenario-sessions`. Start the session and call `/evaluate-next` once per event. Each call releases the next stimulus and records the model's assessment; unreleased stimuli are withheld by the gateway. Inspect the session's released events and recorded assessments after each step.

This is a scenario demonstration protocol, not a report of a completed real-world exercise. Do not present simulated inputs as documentary evidence or pre-fill expected outcomes as actual results.

## Submission evidence still needed

1. A reproducible, lawfully shareable country-document corpus with provenance and appropriate redistribution permissions.
2. A demonstrated ITU-compatible distributed/vector knowledge-base ingestion path and any Sandbox model-training evidence required by the organizers.
3. Recorded real outcomes for the chosen domain and progressively released scenario; report latency, citation coverage, failures and unresolved gaps.
4. The organizer's technical report template (maximum five pages) and demo video as required for the applicable round.

Official references: [Y.3172](https://www.itu.int/rec/T-REC-Y.3172/en) and [AI Readiness Report 2.0](https://www.itu.int/dms_pub/itu-t/opb/ai4g/T-AI4G-AI4GOOD-2025-6-PDF-E.pdf).
