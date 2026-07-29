<div align="center">

# CortexOS

**An AI Engineering Intelligence platform that reasons over your repository — not just your prompt.**

Ask questions, investigate changes, and understand architecture over real code,
using the *minimum sufficient context* for each task.

[Quick start](#quick-start) · [Architecture](docs/ARCHITECTURE.md) · [API](docs/API.md) · [Deployment](docs/DEPLOYMENT.md) · [Contributing](CONTRIBUTING.md)

![status](https://img.shields.io/badge/status-v1.0.0-blue)
![backend](https://img.shields.io/badge/backend-FastAPI%20%C2%B7%20Python%203.12-3776AB)
![frontend](https://img.shields.io/badge/frontend-Next.js%2014%20%C2%B7%20TypeScript-000000)
![db](https://img.shields.io/badge/db-PostgreSQL%20%C2%B7%20pgvector-336791)
![models](https://img.shields.io/badge/models-Ollama%20(local%2C%20zero--cost)-000000)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

---

## Overview

CortexOS indexes a Git repository **once** into a knowledge graph, then builds
every capability on the same kernel: repository chat, architecture exploration,
a Change Impact Guard for pull requests, and deterministic engineering-intelligence
analyses (dead code, dependency cycles, hotspots). Every answer is **grounded in
repository evidence** — files, functions, dependency chains — rather than generic
LLM output.

Its research contribution is **inference efficiency**: an Adaptive Context
Compiler and an Inference Budget Controller decide the smallest context and the
fewest model calls needed for each task, measured against a conventional
fixed-top-K RAG baseline on the same repository and models. It runs fully local
and zero-cost on Ollama, and deploys to the cloud by configuration alone.

## Vision

Give every developer an assistant that understands the *whole* codebase the way
an experienced staff engineer does — its architecture, dependencies, execution
flow, and the blast radius of a change — while spending the least compute
necessary to be correct.

## Key capabilities

| Capability | What it does |
|---|---|
| **Repository chat** | Persistent, repo-scoped conversations answered from the graph, with the evidence used. |
| **Change Impact Guard v2** | Turns a diff or GitHub PR into a grounded impact report: blast radius, risk, per-dimension impact (API/DB/frontend/worker/…), dependency-chain evidence, structured confidence, follow-ups, and revision-over-revision comparison. |
| **Engineering Intelligence** | Deterministic graph analyses — dead code, circular dependencies, hotspots, coupling, architecture layers, request-flow tracing — each with evidence. |
| **Architecture Explorer** | A live, file-level dependency map generated from the ingested graph. |
| **Cross-language graph** | Python + JavaScript/TypeScript (incl. React/Next.js), with `tsconfig`/`jsconfig` alias resolution for monorepos. |
| **Adaptive execution** | Fast path for simple questions, deep path for structural ones — every inference decision recorded and measurable. |

## Screenshots & demo

> Placeholders — capture from a running instance. See [docs/DEMO.md](docs/DEMO.md)
> for the exact shot list and a 3–5 minute demo script.

| Chat | Change Impact Guard | Architecture & Intelligence |
|---|---|---|
| _`docs/assets/chat.png`_ | _`docs/assets/impact.png`_ | _`docs/assets/architecture.png`_ |

Demo GIF: _`docs/assets/demo.gif`_ (placeholder)

## Technology stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic, httpx.
- **Frontend:** Next.js 14, React, TypeScript, Tailwind CSS.
- **Database:** PostgreSQL + `pgvector` (knowledge, embeddings, executions, job queue — one database, no extra services).
- **Models:** Ollama (default, local, zero-cost) behind a provider abstraction (`qwen2.5:3b-instruct` + `nomic-embed-text`).
- **Infra:** Docker Compose (local), Render blueprint + Vercel (cloud), GitHub Actions CI.

## High-level architecture

```text
CortexOS Studio (Next.js, Vercel)      — chat, PR review, architecture, insights
        │  REST + Server-Sent Events
CortexOS Runtime API (FastAPI)         — profiling · retrieval · context
        │                                compilation · SVM · impact · insights
cortex-worker                          — repository ingestion + benchmarks
        │
PostgreSQL + pgvector                  — knowledge graph, embeddings, queue
        │
Model provider (Ollama, external)      — generation + embeddings
```

The kernel pipeline for a question:
**Task Profiler → Inference Budget Controller → Requirement Generator → Hybrid
Retrieval → Context Compiler → Model → Sufficiency Evaluator** (one bounded
expansion retry). Full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

**Prerequisites:** Docker + Docker Compose. (First run pulls a few GB of models.)

```bash
git clone https://github.com/Krutikaa04/CortexOS.git
cd CortexOS
cp .env.example .env          # set CORTEX_DB_PASSWORD at minimum
docker compose up             # db + model runtime + migrations + api + workers
```

- API: http://localhost:8000 · health: http://localhost:8000/health
- Then run Studio (below) and open http://localhost:3000.

Health shows `degraded` until the models finish pulling — that is expected.

## Local development

**Backend + workers (hot reload) via Docker:**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This maps the DB (`5432`) and model runtime (`11434`) to localhost, mounts the
source for reload, and starts Studio at http://localhost:3000.

**Backend tests / lint (host Python):**

```bash
cd api
pip install -e ".[dev]"
ruff check cortex tests
python -m pytest -q
```

**Frontend (host Node):**

```bash
cd studio
npm install
npm run dev            # http://localhost:3000
# NEXT_PUBLIC_CORTEX_API_URL defaults to http://localhost:8000
```

**Workers** are the `cortex-worker` (ingestion) and `cortex-worker-benchmark`
(benchmarks) services in Compose. To run one on the host:

```bash
cd api
CORTEX_WORKER_KINDS=ingest_source python -m cortex.worker
```

## Environment variables

Full list and defaults live in [`.env.example`](.env.example). Essentials:

| Variable | Purpose |
|---|---|
| `CORTEX_DB_URL` | PostgreSQL URL (managed `postgres://…?sslmode=require` is normalized + TLS auto-applied). |
| `CORTEX_MODEL_BASE_URL` | Ollama-compatible endpoint. |
| `CORTEX_MODEL_PROVIDER` | Model provider (`ollama`, default). |
| `CORTEX_ENV` | `dev` \| `production` (tightens CORS + DB TLS). |
| `CORTEX_ALLOWED_ORIGINS` | Exact browser origins allowed in production (the Studio URL). |
| `CORTEX_API_TOKEN` | If set, requires `Authorization: Bearer <token>` on all non-health endpoints. |
| `CORTEX_GIT_TOKEN` | Token for cloning private https repositories. |
| `NEXT_PUBLIC_CORTEX_API_URL` | Frontend → backend base URL (set in Vercel). |

## Deployment

The same codebase runs locally and in the cloud — only configuration differs.
Frontend → Vercel; API + worker → Render (or any container host); database →
any managed PostgreSQL with `pgvector`. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the step-by-step guide, the
`render.yaml` blueprint, and the production checklist.

## API overview

REST under `/v1`, plus `/health` and `/health/live`. Live execution events
stream over Server-Sent Events. Every endpoint, request/response shape, and
error is documented in [docs/API.md](docs/API.md).

## Folder structure

```text
api/                     FastAPI control plane + worker (Python)
  cortex/kernel/         Profiler · Budget Controller · Retriever · Compiler ·
                         Sufficiency · Change Impact Guard · Engineering Insights
  cortex/svm/            Semantic Virtual Memory (session working memory)
  cortex/ingestion/      repo → artifacts + edges + embeddings (Python & JS/TS)
  cortex/providers/      model provider abstraction (Ollama)
  cortex/routes/         HTTP endpoints
  cortex/baseline/       conventional top-K RAG baseline
  cortex/benchmark/      paired benchmark harness
  alembic/               database migrations
  tests/                 unit tests
studio/                  Next.js frontend (chat, PR review, architecture, graph)
docs/                    architecture, API, deployment, demo, portfolio
handbook/                internal design context (research/design source of truth)
infra/                   container entrypoints
.github/workflows/       CI (lint · types · tests · builds · docker)
docker-compose*.yml      local orchestration
render.yaml              production blueprint
```

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `/health` → `503 unavailable` | Database unreachable — check `CORTEX_DB_URL` / `CORTEX_DB_SSL`. |
| `worker: none` / `stale` in `/health` | Worker not running or can't reach DB/model. |
| `models: unreachable` | Model provider down or wrong `CORTEX_MODEL_BASE_URL`. |
| Ingestion returns `422` | Repository URI failed validation (production allows only remote git URIs). |
| Studio can't reach API in prod | Set `CORTEX_ALLOWED_ORIGINS` to the Studio origin and `NEXT_PUBLIC_CORTEX_API_URL` to the API URL. |

## Roadmap

Shipped through **v1.0**: repository chat with sessions, cross-language graph,
Change Impact Guard v2, engineering intelligence, streaming provider,
production hardening (auth, validation, health, CI). See [CHANGELOG.md](CHANGELOG.md).

**Future work:** end-to-end token streaming in chat, a dedicated Bug
Investigator flow, repository-aware code generation, rate limiting + metrics
export, and published benchmark numbers.

## License

[MIT](LICENSE).
