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

## Repository layout

```text
handbook/   locked project definition and design context
api/        FastAPI control plane + worker (Python)
studio/     CortexOS Studio frontend (Next.js)
infra/      container entrypoints and infra scripts
```
