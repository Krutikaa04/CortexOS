# PART 09 — TECH STACK, DOCKER, AND ZERO-COST CONSTRAINT

## 1. Locked constraints

### Docker-first
Every major service must be containerized.

### Zero mandatory cost
The project budget is locked at ₹0 for the required implementation path.

### Local-first AI
The core system must work without a commercial API key.

---

## 2. Current planned stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- Framer Motion
- React Flow
- D3.js
- Recharts

### Backend / control plane
- Python
- FastAPI
- Pydantic

### Database / vectors
- PostgreSQL
- pgvector

### Local AI
- Ollama
- open-source local instruction models
- open-source embedding models

### Observability
- OpenTelemetry
- custom CortexOS event store

### Containerization
- Docker
- Docker Compose

The exact versions and libraries are not yet locked.

---

## 3. Intended container architecture

Conceptual services:

```text
cortex-web
  Next.js frontend

cortex-api
  FastAPI control plane

cortex-worker
  asynchronous AI / ingestion worker

cortex-db
  PostgreSQL + pgvector

cortex-model-runtime
  local model integration

cortex-observability
  telemetry and runtime events
```

Exact boundaries remain unresolved.

---

## 4. Required developer experience

Target:

```text
git clone
  ↓
configure environment
  ↓
docker compose up
  ↓
CortexOS running
```

The repository should be reproducible on another developer's machine.

---

## 5. Docker topics still to design

- development images,
- production images,
- multi-stage builds,
- health checks,
- persistent volumes,
- network isolation,
- environment validation,
- startup dependencies,
- model availability checks,
- database migrations,
- seed data,
- demo mode,
- benchmark mode,
- resource limits,
- CPU-only compatibility,
- RAM requirements,
- image size strategy.

---

## 6. Zero-cost restrictions

No core feature may require:
- paid LLM APIs,
- paid databases,
- paid vector databases,
- paid hosting,
- paid observability,
- paid authentication,
- paid storage,
- paid queues,
- paid monitoring.

Optional provider integrations may exist later, but cannot be required for:
- development,
- testing,
- benchmarking,
- core demonstrations,
- recruitment evaluation.

---

## 7. Zero-cost architecture principles

Prefer:
- open source,
- local execution,
- self-hosting,
- free tiers only where reliable,
- provider independence,
- CPU-compatible paths,
- replayable real traces for public demos.

---

## 8. Public deployment challenge

A large stack containing:
- Next.js,
- FastAPI,
- PostgreSQL,
- vector search,
- workers,
- local models,
- persistent storage,

cannot simply be assumed to run permanently on free cloud infrastructure.

Therefore the likely deployment split is:

```text
PUBLIC DEMO LAYER

Hosted frontend
+ lightweight public API where feasible
+ recorded real benchmark traces
+ interactive replay
+ small live demonstrations if feasible

FULL CORTEXOS RUNTIME

Dockerized
+ runs locally
+ full AI inference
+ full benchmarks
+ full knowledge ingestion
```

Recorded traces must originate from real executions. The public demo must not fake results.

The exact free hosting providers must be researched later because free-tier offerings change over time.

---

## 9. Important cost principle

“Zero cost” means zero mandatory monetary expenditure, not zero hardware usage.

The student may use an existing personal machine for:
- local inference,
- benchmarking,
- Docker,
- model execution.

The project should still define minimum hardware expectations and CPU-only fallback behavior.

---

## 10. Model strategy remains open

Need to select:
- embedding model,
- small task model,
- main reasoning model,
- evaluator model,
- CPU-compatible model set,
- model abstraction interface,
- routing rules.

Model selection must be based on:
- license,
- local feasibility,
- RAM,
- speed,
- quality,
- reproducibility.
