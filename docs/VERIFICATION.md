# Integration verification — 10 November 2026

The intended flow is: conversation → same-origin gateway → authenticated backend → queue worker → private Qwen route → six persisted assessments → readable synthesis → cited follow-up.

## Checks completed

| Boundary | Evidence | Result |
| --- | --- | --- |
| Frontend production output | Vite build plus packaged Worker entrypoint | Passed |
| Gateway and response contracts | 26 Node tests: authentication, same-origin mutations, six follow-up roles, private model relay, citation validation, source resolution, deletion refusal | Passed with controlled test fixtures |
| Backend regression suite | 495 Python tests and two subtests, including provenance, evidence, policy comparisons, autonomous advisory execution, durable model routing and live-check failure handling | Passed; one upstream Starlette/httpx deprecation warning |
| Agent inspection | Browser: six explained cards, selecting a card opens the corresponding detail, no synthetic execution events | Passed in available preview |
| Navigation and reading | Browser: narrower integrated black navigation, main-area scrolling, thin dark scrollbar, no fixed right agent sidebar | Passed in available desktop preview |
| Deletion contract | Existing authenticated DELETE route; prior isolated TestClient create/delete/history check; gateway regression preserves active-job refusal and cross-origin protection | Passed in isolated test environment |
| Live Qwen and complete cited investigation | Requires the actual model, worker and documentary archive on the user's laptop | Not rerun from this remote environment |
| Hosted Site → upstream API | Site runtime has no `UNICRON_API_URL` configured | Not connected; UI honestly reports backend unavailable |

A build or fixture-based test is not evidence that the hosted model is reachable. No test output should be described as a completed live regulatory investigation.

## Run the actual local check

After updating and restarting the laptop checkout, use the **frontend** origin printed by the launcher:

```bash
python3 scripts/verify-live.py --base http://127.0.0.1:YOUR_FRONTEND_PORT
```

Replace `YOUR_FRONTEND_PORT` with the printed number. This performs real inference, checks model-backed question routing, creates a retained verification case, waits for its worker, checks all six stages and persisted events, and asks a documentary follow-up. It resolves exact source references against verified provenance. It fails if any of these checks cannot be established, including an answer without verified documentary citations. It does not verify legal correctness.

To inspect the latest job from an existing case instead of creating one:

```bash
python3 scripts/verify-live.py --base http://127.0.0.1:YOUR_FRONTEND_PORT --case-id YOUR_CASE_ID
```

This still calls the actual model for readiness and follow-up checks. A timeout leaves the case and job intact; inspect activity before creating additional work.

## External requirements

The official [hackathon requirements](https://aiforgood.itu.int/event/ai-for-good-sandbox-hackathon-united-arab-emirates/) were rechecked. See [the requirement matrix](REQUIREMENTS.md). ITU-hosted distributed/vector ingestion, Sandbox fine-tuning, a licensed shareable country corpus, and submission report/video evidence are not completed by changing the frontend. They remain external delivery work and must not be advertised as implemented or certified.
