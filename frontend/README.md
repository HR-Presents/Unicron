# UNICRON conversational workspace

React 19 + Vite, with react-markdown and a server-side API gateway. The UI is implemented in `src/main.jsx`, `src/workspace.css` and `src/ResponseData.jsx`. `src/live-api.mjs` reads the actual API and execution events. The old dashboard and 3D interface have been removed. General chat and automatic investigation classification use the preserved laptop gateway; follow-ups include structured conversation context.

Run `npm ci` then `npm run dev`. Set server-side values from `.env.example` using environment variables or an ignored `.env.local` file. For local all-service startup use `../start.sh`, which wires its dynamically allocated API port automatically.

Use `UNICRON_MODEL_VIA_BACKEND=1` to avoid exposing a separate Qwen endpoint. The backend's durable model router controls inference using its configured local Qwen endpoint. Direct server-side model connection remains available when relay mode is disabled. No secrets are sent to browser JavaScript.

`npm run build` produces the client and Worker gateway. `npm test` validates the active agent/API contracts, authentication, source restrictions, citation allowlists and backend relay. Agent status comes from recorded backend events; activity is never simulated. Conversations created in this browser persist locally; investigation/run history comes from the API. The current API returns JSON, so response streaming is not advertised.
