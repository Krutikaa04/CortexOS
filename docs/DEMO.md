# Demo guide

A repeatable script for a 3–5 minute walkthrough or a recorded demo. Screenshots
referenced here are **placeholders** — capture them from a running instance.

## Sample repositories

Small, dependency-light, fast to ingest:
- `https://github.com/pallets/itsdangerous` (Python — signing/security; great for impact + auth sensitivity)
- `https://github.com/pallets/click` (Python — larger call graph)
- A small Next.js/React app of your choice (to show JS/TS + `tsconfig` alias resolution)

## Sample pull requests / diffs

- The Pull Requests page ships a **"Load example diff"** button (a change to
  `itsdangerous`'s `Signer.unsign`) — ideal for a first impact demo.
- For the GitHub-PR path, use any open PR on a public repo you've ingested,
  e.g. `https://github.com/pallets/itsdangerous/pull/<n>`.
- To show **revision comparison**, analyze the same PR URL twice (or two related
  diffs) and highlight new/resolved risks and blast-radius delta.

## 3–5 minute demo flow

1. **Ingest (30s).** Repositories → add `itsdangerous` → show the job progress →
   ready. _Shot: `repositories.png`._
2. **Chat (60s).** Ask "Where is the signature validated?" → point out the
   grounded answer, the **Relevant files & functions** evidence, and the live
   runtime panel (context reduction, model calls, latency). Ask a follow-up to
   show **session memory**. _Shot: `chat.png`._
3. **Change Impact Guard (90s).** Pull Requests → Load example diff → Analyze →
   walk the report top to bottom: risk banner, **confidence explanation**,
   **impact by dimension**, **dependency-chain evidence**, follow-ups. Re-run to
   show **revision comparison**. _Shot: `impact.png`._
4. **Architecture & Engineering Intelligence (45s).** Architecture → the live
   dependency graph, then the intelligence panel: hotspots, coupling, circular
   dependencies, potential dead code — each with evidence. _Shot: `architecture.png`._
5. **Close (15s).** Note it ran fully local/zero-cost on Ollama and deploys to
   the cloud by configuration.

## Screenshots to capture

`repositories.png` · `chat.png` · `impact.png` · `architecture.png` ·
`graph.png` · optional `settings.png` (health/diagnostics). Store under
`docs/assets/` and update the README table.

## Recording checklist

- [ ] Models fully pulled (`/health` → `models: ok`) so there is no first-call delay.
- [ ] A repository already ingested and `ready`.
- [ ] Worker running (`/health` → `worker: alive`).
- [ ] Dark theme, clean browser window, 1280×800+.
- [ ] Rehearse the four clicks above; keep narration to the "why", not the UI.
- [ ] Export a short `demo.gif` of steps 2–3 for the README.
