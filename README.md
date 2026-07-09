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
cortex-worker                      — ingestion & benchmark jobs
        │
PostgreSQL + pgvector              — knowledge, embeddings, traces, queue
Ollama                             — local open-source models (CPU-friendly)
```

Everything runs locally through Docker Compose at zero mandatory cost.
The Studio frontend additionally deploys to Vercel as a public demo that
replays *real* recorded execution traces.

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
- **Replay Demo** — recorded real traces replayed through the same
  components (this is what the public Vercel deployment shows)

Local dev: `npm install && npm run dev` in `studio/` (or use the dev
compose profile). Vercel deployment uses `NEXT_PUBLIC_DEMO_MODE=1` and
bundles exported traces in `studio/public/traces/`.

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
