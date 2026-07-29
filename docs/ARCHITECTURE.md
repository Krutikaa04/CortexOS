# CortexOS Architecture

This document describes the **implemented** system. It does not describe planned
or hypothetical components.

## System overview

```text
┌─────────────────────────┐     REST + SSE     ┌──────────────────────────────┐
│ CortexOS Studio (Next.js)│ ─────────────────▶ │ Runtime API (FastAPI)         │
│ chat · PR review · graph │                    │ routes · kernel · providers   │
└─────────────────────────┘                    └───────────────┬──────────────┘
                                                                │ SQLAlchemy (async)
        ┌───────────────────────────────────────────────────────┼──────────────┐
        │                                                        ▼              │
┌───────────────┐    claims jobs (SKIP LOCKED)      ┌────────────────────────┐  │
│ cortex-worker │ ◀───────────────────────────────▶ │ PostgreSQL + pgvector  │  │
│ ingestion     │                                   │ graph · embeddings ·   │  │
│ + benchmarks  │                                   │ executions · job queue │  │
└──────┬────────┘                                   └────────────────────────┘  │
       │ generation / embeddings                                                │
       ▼                                                                        │
┌───────────────┐                                                               │
│ Model provider│ ◀─────────────────────────────────── API (chat, impact) ──────┘
│ (Ollama)      │
└───────────────┘
```

**One database carries everything** — knowledge graph, embeddings, executions,
event stream, chat sessions, and the job queue. There is no external queue or
cache service.

## Components

### Knowledge Graph
The unit of knowledge is a **semantic artifact** — a structural unit
(module / class / function / method / doc section) with stable identity, source
span, extracted facts, and multiple representations. Artifacts are connected by
typed **edges** (`calls`, `imports`, `inherits`, `contains`, `references_doc`,
`documents`). Stored in `semantic_artifact` and `artifact_edge`. This graph is
language-agnostic, so every capability built on it (chat, architecture, impact,
insights) works across languages.

### Repository ingestion pipeline
`FETCH → ENUMERATE → PARSE → LINK → EMBED → BASELINE → FINALIZE`, run by the
worker as an idempotent, resumable job (every write is an upsert keyed on
`(source_version_id, …)`; the commit SHA is pinned on first run). Structural
parsing is deterministic — Python via the stdlib `ast`, JavaScript/TypeScript
(incl. JSX and `tsconfig`/`jsconfig` alias resolution) via a dependency-free
parser — so code facts are always grounded, never hallucinated. Source versions
are append-only; re-ingesting a commit supersedes the previous version and
invalidates stale Semantic-Virtual-Memory pages.

### Adaptive Context Compiler
Turns retrieved candidate artifacts into the **minimum sufficient context** for
a task: it selects representations (raw code vs. compressed facts), deduplicates,
and packs against a token budget derived from the task profile. It reports the
real reduction versus the raw candidate tokens.

### Inference Budget Controller
The deterministic core of CortexOS's efficiency contribution. Before any
optional, expensive operation it answers one question — *should this inference
happen, or can a cheaper deterministic path produce an equivalent result?* —
and records a typed `BudgetDecision`. **Rule: no LLM call ever decides whether
to make an LLM call.** Routing is a pure function of the task profile (fast path
for simple factual questions skips model-based requirement decomposition; deep
path keeps it), so the same question always takes the same, measurable path.

### Semantic Virtual Memory (SVM)
Treats the context window as managed working memory over a session. Artifacts
become **pages** that stay resident across turns of a conversation (stable,
append-only prefix), so the model runtime reuses its KV cache and later turns
only pay for new pages. Memory pressure triggers eviction; re-ingestion
invalidates pages. Scoped per chat session.

### Change Impact Guard (v2)
CortexOS's flagship task. A diff (pasted or fetched from a GitHub PR) becomes a
grounded impact report by reusing the kernel:

```text
diff ─parse─▶ changed artifacts ─reverse-BFS over dependency edges─▶ blast radius
     │                                                                    │
     ▼                                             deterministic reasoning ▼
  Context Compiler (changed + impacted) ─▶ ONE model call ─▶ narrative + report
```

The structural work is deterministic graph traversal (zero inference). Only the
human-readable narrative costs one model call. The report includes: risk level +
reasons, direct/indirect impact, **impact by engineering dimension**
(API / database / configuration / frontend / background-worker / external-service
/ auth / caching / architectural), **dependency-chain evidence** (why each
dependent is affected), **structured confidence** (each factor a measured graph
fact), recommended tests, suggested follow-ups, and — when a PR is re-analyzed —
a **revision comparison** (new/resolved risks, blast-radius delta, risk trend).

### Engineering Intelligence
Deterministic analyses over the same graph, no model calls:
- **Dead code** — functions/classes with no inbound dependency edge and not an entrypoint, with evidence.
- **Circular dependencies** — file-level cycle detection with risk + resolution.
- **Repository insights** — large modules, high-coupling files, hotspots (most-referenced), architecture-layer distribution.
- **Request-flow tracing** — forward traversal from an entrypoint through `calls`/`imports`.

### Model provider abstraction
The kernel talks to models only through `ModelProvider` (generate, embed,
streaming, health). Ollama is the default, local, zero-cost implementation;
the deployment target selects a provider by configuration. Nothing else in the
codebase depends on Ollama directly.

## Request lifecycle (a chat question)

1. `POST /v1/executions` inserts an execution row (`running`) and starts a
   background task; returns immediately.
2. Kernel: **Task Profiler** classifies the question → **Budget Controller**
   picks fast/deep path → **Requirement Generator** (model call only on deep
   path) → **Hybrid Retrieval** (vector + graph) → **Context Compiler** →
   **model generation** → **Sufficiency Evaluator** (one bounded expansion
   retry if under-grounded).
3. Every stage emits a typed event; Studio consumes them live via
   `GET /v1/executions/{id}/stream` (Server-Sent Events).
4. The final answer + measured metrics (tokens, reduction %, model calls,
   latency, budget decisions) are persisted on the execution row.

## Worker architecture
The database **is** the queue. Workers claim jobs with
`SELECT … FOR UPDATE SKIP LOCKED`, kind-filtered by lane
(`CORTEX_WORKER_KINDS`), so a long benchmark never blocks ingestion. Crashed
workers are recovered by lease expiry; cancellation is cooperative via
checkpoints; each worker heartbeats for health reporting. Graceful shutdown
disposes the connection pool.

## Data model (core tables)
`source` · `source_version` · `source_file` · `semantic_artifact` ·
`artifact_edge` · `artifact_embedding` · `baseline_chunk` · `execution` ·
`execution_event` · `chat_session` · `job` · `worker_heartbeat`. Managed by
Alembic migrations (`api/alembic/versions`, `0001` → `0005`).
