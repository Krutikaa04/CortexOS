# CortexOS — portfolio summary

Recruiter- and interview-facing framing. Every claim below is supported by the
implementation; no metrics are asserted until the benchmark harness produces
them on a specific repository + model pair.

## Elevator pitch

> CortexOS is an AI engineering-intelligence platform that indexes a repository
> into a knowledge graph and answers real engineering questions — repository
> chat, change-impact analysis, architecture and dependency insights — grounded
> in code evidence, while spending the minimum context and model calls per task.
> It runs fully local and zero-cost on Ollama and deploys to the cloud by
> configuration alone.

## Resume-ready summary

**CortexOS — AI Engineering Intelligence Platform** (Python/FastAPI, Next.js/
TypeScript, PostgreSQL/pgvector, Ollama, Docker, Render/Vercel). Designed and
built an end-to-end system that ingests a Git repository into a cross-language
knowledge graph and reuses one kernel for repository chat, a Change Impact Guard
for pull requests, and deterministic engineering-intelligence analyses. Built an
Adaptive Context Compiler and an Inference Budget Controller to minimize context
size and model calls, benchmarked against a fixed-top-K RAG baseline. Shipped
production hardening (auth, input validation, health/observability, CI) and full
cloud deployment.

## Technical highlights

- **Graph-grounded reasoning, not prompt stuffing.** A typed knowledge graph
  (artifacts + `calls`/`imports`/`inherits`/… edges) drives every feature;
  answers cite files, functions, and dependency chains.
- **Deterministic efficiency core.** The Inference Budget Controller routes each
  task on a pure function of its profile — "no LLM call decides whether to make
  an LLM call" — and records every decision, so cost is auditable and
  reproducible.
- **Change Impact Guard v2.** Reverse-BFS blast radius over the graph +
  per-dimension impact classification + dependency-chain evidence + structured
  confidence, with exactly **one** model call per analysis and revision-over-
  revision comparison of persisted PR reports.
- **Cross-language accuracy.** A dependency-free JS/TS parser plus
  `tsconfig`/`jsconfig` baseUrl+paths alias resolution (monorepo-scoped) makes
  the graph resolve across real Next.js apps.
- **Systems design.** The database is the job queue (`FOR UPDATE SKIP LOCKED`,
  kind-partitioned lanes, lease-based crash recovery); Semantic Virtual Memory
  keeps conversation pages resident for KV-cache reuse; ingestion is idempotent
  and resumable.

## Engineering challenges solved

- **Grounding vs. hallucination:** structural facts come from deterministic
  parsers (Python `ast`, JS/TS scanner), never the model, so evidence is real.
- **Latency/cost control:** fast/deep routing and a token-budgeted compiler cut
  unnecessary inference while a sufficiency evaluator guards answer quality with
  a single bounded retry.
- **Cross-language, monorepo dependency resolution** without a heavy toolchain.
- **Production safety on a code-cloning service:** validated repo URIs/refs
  (argument-injection / `file://` / path-traversal protection), optional bearer
  auth, and TLS-aware managed-Postgres connectivity.

## Measurable achievements

The benchmark harness measures — per repository/model — **context-token
reduction**, **model-call count**, and **latency** for the CortexOS kernel
versus the fixed-top-K RAG baseline, from real executions (token counts come
from the model runtime, not estimates). Report the numbers you reproduce rather
than quoting figures here.
