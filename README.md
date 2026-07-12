# CortexOS

**A Docker-first, zero-cost, model-agnostic adaptive inference runtime.**

CortexOS reduces Generative AI resource consumption by determining, compiling,
and allocating the *minimum sufficient context* and compute needed for each
task while preserving a target answer quality. Its two signature systems are
the **Context Compiler** (turns retrieved knowledge into a minimal,
requirement-aware context) and **Semantic Virtual Memory** (treats the LLM
context window as managed working memory over a wider semantic address space).

First use case: **repository question-answering and change-impact analysis**
("will changing the auth middleware affect payments?"), benchmarked against a
conventional fixed top-K RAG baseline on the same repository and models.

> Status: early implementation. No performance claims are made until the
> benchmark harness produces real numbers. See `handbook/` for the full
> project definition.

## Architecture

```text
CortexOS Studio (Next.js)          — visual control & observability frontend
        │
CortexOS Runtime API (FastAPI)     — task profiling, retrieval, context
        │                            compilation, SVM, execution, events
cortex-worker                      — ingestion lane (ingest_source jobs)
cortex-worker-benchmark            — benchmark lane (run_benchmark jobs)
        │
PostgreSQL + pgvector              — knowledge, embeddings, traces, queue
Ollama                             — local open-source models (CPU-friendly)
```

Workers claim jobs by lane (`CORTEX_WORKER_KINDS`), so a long-running
benchmark can never block repository ingestion. Jobs are inspectable and
cooperatively cancellable:

```bash
GET  /v1/jobs/{id}          # status, stage, honest done/total progress
POST /v1/jobs/{id}/cancel   # queued → cancelled; running → cancellation_requested,
                            # acknowledged at the worker's next safe checkpoint
```

Interactive questions route deterministically: simple factual questions take
a **fast path** (heuristic requirements, one embedding batch, one generation
call), while structural and change-impact questions keep the full deep
pipeline. Every execution's metrics record the path, per-stage timings,
model-call counts, and each skip/execute/escalate decision with its reason.

Everything runs locally through Docker Compose at zero mandatory cost.
Studio always talks to a live runtime and every number it shows comes from
a real execution — there is no replay, demo, or prerecorded-trace mode.

## Quick start

Requirements: Docker, ~8 GB RAM, ~15 GB free disk. No GPU, no API keys.

```bash
git clone <this repo>
cd CortexOS
cp .env.example .env       # set CORTEX_DB_PASSWORD
docker compose up
```

First start pulls the local models (a few GB); the API reports
`status: degraded` at `http://localhost:8000/health` until the pull
completes, then `ok`.

Development mode (hot reload + local Studio on :3000):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## CortexOS Studio

The Studio (`studio/`, Next.js) is the visual control plane:

- **Command Center** — runtime health, sources, latest benchmark headline
- **Playground** — ask a question and get the answer with proof of cost: by
  default every question also runs through a conventional RAG pipeline, and
  a savings card shows the measured token difference priced at public
  commercial API list rates (clearly labeled — CortexOS itself runs locally
  for ₹0). Runtime decisions are one click away; optional SVM session mode
  keeps memory pages resident across questions
- **Context X-Ray** — per-execution: requirements, included artifacts with
  representation levels, rejected artifacts *with reasons*, token savings
- **Benchmark Lab** — paired baseline-vs-cortex suites with honest metrics

Local dev: `npm install && npm run dev` in `studio/` (or use the dev
compose profile). Studio requires a reachable runtime API
(`NEXT_PUBLIC_CORTEX_API_URL`); it has no offline demo fallback.

## Benchmarking

```bash
# after ingesting a repository:
curl -X POST localhost:8000/v1/benchmarks -H 'content-type: application/json' \
     -d '{"suite": "demo_store"}'
```

Both pipelines run the same questions on the same snapshot with the same
models; token counts come from the model runtime itself. No performance
number is claimed anywhere unless it came from such a run.

## Repository layout

```text
handbook/   locked project definition and design context
api/        FastAPI control plane + worker (Python)
  cortex/kernel/     Task Profiler · Requirement Generator · Hybrid
                     Retriever · Context Compiler · Sufficiency Evaluator
  cortex/svm/        Semantic Virtual Memory (pages, faults, eviction)
  cortex/baseline/   conventional top-K RAG baseline
  cortex/benchmark/  paired benchmark harness + suites
  cortex/ingestion/  repository → semantic artifacts + edges + embeddings
studio/     CortexOS Studio frontend (Next.js)
infra/      container entrypoints and infra scripts
```
