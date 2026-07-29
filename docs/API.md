# CortexOS API

Base URL: `http://localhost:8000` (local) or your deployed API URL. Interactive
docs are served at `/docs` (Swagger) and `/redoc`.

## Authentication

Auth is **optional and configuration-gated**. When `CORTEX_API_TOKEN` is set,
every endpoint except `/health*` requires:

```
Authorization: Bearer <CORTEX_API_TOKEN>
```

Missing/incorrect token → `401 {"detail": "unauthorized"}`. When the variable
is empty (local dev), the API is open.

## Conventions

- JSON request/response bodies. IDs are UUID strings.
- Long-running work returns `202` with a job/execution id and is polled or
  streamed.
- Errors use standard status codes with `{"detail": "..."}` (FastAPI/Pydantic
  validation errors return `422`).

---

## Health

### `GET /health/live`
Liveness — process is up, no dependencies checked.
```json
{ "status": "alive", "version": "1.0.0" }
```

### `GET /health`
Readiness + diagnostics. `200` with `ok`/`degraded`; `503 unavailable` when the
database is unreachable.
```json
{
  "status": "ok", "version": "1.0.0", "ready": true,
  "checks": {
    "api": "ok", "database": "ok", "worker": "alive",
    "repository_indexer": "ready", "queue": "0 queued, 0 running",
    "model_provider": "ollama", "models": "ok"
  }
}
```

---

## Sources & ingestion

### `POST /v1/sources`
Queue ingestion of a Git repository.
```json
{ "uri": "https://github.com/pallets/itsdangerous", "ref": null, "display_name": null }
```
`202 → { "job_id": "<uuid>", "status": "queued" }`.
`422` if the URI fails validation (argument injection, `file://`, or — in
production — a local path).

### `GET /v1/sources`
List sources with their latest version (status, commit, stats).

### `GET /v1/jobs/{job_id}` · `POST /v1/jobs/{job_id}/cancel`
Job status (stage + progress) and cooperative cancellation.
(`GET /v1/sources/jobs/{job_id}` is a compatibility alias.)

---

## Executions (chat / Q&A)

### `POST /v1/executions`
Run a question through a pipeline.
```json
{ "query": "Where is the signature validated?", "mode": "cortex",
  "source_version_id": null, "session_id": null }
```
- `mode`: `cortex` (adaptive kernel) or `baseline` (fixed top-K RAG).
- `source_version_id`: defaults to the latest ready version.
- `session_id`: links the turn to a chat session (SVM working memory).

`202 → { "execution_id": "<uuid>", "status": "running" }`.

### `GET /v1/executions/{id}`
Final result: `answer`, `status`, `failure_reason`, and `metrics` (input/output
tokens, `context_reduction_pct`, `model_calls`, `total_ms`, `path`, `intent`,
budget `decisions`, …).

### `GET /v1/executions/{id}/events`
The full typed event list for an execution.

### `GET /v1/executions/{id}/stream`
**Server-Sent Events** of the live pipeline until completion (event per stage;
terminal `DONE`).

---

## Chat sessions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/sessions` | Create a repo-scoped conversation. Body: `{ "source_version_id", "title"? }`. |
| `GET` | `/v1/sessions?source_version_id=<id>` | List conversations (title, message_count, last_activity). |
| `GET` | `/v1/sessions/{id}/messages` | Transcript reconstructed from executions (query, answer, metrics, evidence files). |
| `PATCH` | `/v1/sessions/{id}` | Rename. Body: `{ "title" }`. |
| `DELETE` | `/v1/sessions/{id}` | Delete conversation + its messages (`204`). |

---

## Change Impact Guard

### `POST /v1/sources/{version_id}/impact`
Analyze a unified diff. Body: `{ "diff": "<unified diff>" }`.
`202 → { "execution_id", "status": "running" }`. Phases stream over the
execution event feed (mode `impact`); the finished report is the execution's
`metrics`.

### `POST /v1/sources/{version_id}/impact/github`
Fetch a public PR's diff and analyze it. Body: `{ "pr_url": "https://github.com/owner/repo/pull/123" }`.
`422` on a non-PR URL, private/missing PR, or rate limit.

### `GET /v1/sources/{version_id}/impact/history`
Past analyses (reusing persisted impact executions): `risk_level`, `confidence`,
`changed_files`, `pr_url`, `summary`, timestamps.

**Report shape** (in `metrics`): `risk_level`, `risk_reasons`, `confidence`,
`confidence_explanation{score,level,factors[]}`, `sensitivity`, `changed_files`,
`changed_artifacts`, `direct_impact`, `indirect_impact`, `impact_dimensions`,
`dependency_chains`, `architecture_note`, `problems`, `recommended_tests`,
`follow_ups`, `suggested_patch`, `summary`, `revision_comparison?`, `metrics`.

---

## Knowledge graph & architecture

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/sources/{version_id}/graph?limit=&kinds=` | Nodes + typed edges (ranked by connectivity). |
| `GET` | `/v1/sources/{version_id}/architecture` | File-level dependency map (nodes = files, edges = cross-file relationships). |
| `GET` | `/v1/sources/{version_id}/artifacts/{artifact_id}` | Full artifact detail incl. source + GitHub link. |
| `GET` | `/v1/sources/{version_id}/artifacts/{artifact_id}/neighbors` | `depends_on` / `dependents`. |
| `GET` | `/v1/sources/{version_id}/lookup?qualified_name=` | Resolve a qualified name to an artifact. |

---

## Engineering intelligence (deterministic, no model calls)

| Method | Path | Returns |
|---|---|---|
| `GET` | `/v1/sources/{version_id}/insights/dead-code` | Unreferenced functions/classes with evidence. |
| `GET` | `/v1/sources/{version_id}/insights/cycles` | Circular dependencies with risk + resolution. |
| `GET` | `/v1/sources/{version_id}/insights/overview` | Large modules, high coupling, hotspots, architecture layers. |
| `GET` | `/v1/sources/{version_id}/insights/flow?qualified_name=` | Forward request-flow trace from an entrypoint. |

---

## Benchmarks

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/benchmarks/suites` | Available benchmark suites. |
| `POST` | `/v1/benchmarks` | Queue a suite run. |
| `GET` | `/v1/benchmarks` · `/v1/benchmarks/{run_id}` | Runs and results (cortex vs. baseline). |
