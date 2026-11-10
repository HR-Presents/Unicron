# UNICRON frontend

React 19 and Vite 7, with a server-side Worker/local gateway. See the [root README](../README.md) for installation, model configuration, data paths and deployment.

## Experience

- Quiet investigation history and search in the left sidebar.
- Readable conversation, structured findings and source references in the centre.
- A collapsible agent sidebar with six recorded roles and independent responses.
- Selected-agent follow-ups using the existing evidence-role contracts.
- Matte black and porcelain themes, keyboard navigation and reduced-motion support.
- Mobile drawers for navigation and agent inspection.

`src/report-model.mjs` presents known narrative fields and separates evidence limitations from internal workflow metadata. Flagged comparisons are not shown as supported findings. `src/ReportResponse.jsx` resolves exact verified citation passages through the authenticated gateway.

## Commands

```bash
npm ci
npm run dev
npm test
npm run build
```

The recommended full local launch is `../start.sh`, which wires API credentials and its selected backend port automatically. `UNICRON_MODEL_VIA_BACKEND=1` sends routing, chat and follow-up generation through the backend's local model router. Direct model mode remains optional server-side configuration. Do not expose credentials through `VITE_` environment variables.

The build emits client assets and `dist/server/index.js`, a Worker gateway. This is not a standalone static-only app. Case/run history is persisted by the API; browser conversation turns are stored locally. The current gateway returns JSON, so streaming is not advertised.

Navigation can be collapsed. The agent panel starts closed and opens from **Agents**. **Delete chat** is in the conversation header; each investigation also has a trash button in history. Deletion requires confirmation, removes case-owned records through the authenticated backend, and is refused while an investigation is queued or running. Ordinary chat deletion clears browser-local messages.
