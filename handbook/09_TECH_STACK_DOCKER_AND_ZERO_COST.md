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
## 9. Locked Vercel Deployment Requirement

CortexOS Studio must be publicly deployed on Vercel.

Vercel is the required deployment target for:

* the public CortexOS Studio frontend,
* the recruitment-facing project experience,
* interactive execution visualizations,
* benchmark dashboards,
* architecture exploration,
* execution-trace replay,
* Context X-Ray demonstrations,
* Semantic Virtual Memory demonstrations,
* project documentation surfaces,
* and lightweight public functionality compatible with the deployment environment.

The Vercel deployment must remain within the project's zero-mandatory-cost constraint.

The architecture must not assume that the complete CortexOS runtime can execute inside Vercel.

The following components belong to the complete Dockerized runtime and must remain independently executable:

```text
PostgreSQL + pgvector
Local model runtime
Ollama
Long-running AI inference
Knowledge ingestion workers
Benchmark workers
Heavy document processing
Repository processing
Local embedding generation
Full execution orchestration
Resource-intensive experiments
```

The required deployment model is:

```text
                    PUBLIC INTERNET
                           │
                           ▼
                ┌─────────────────────┐
                │      VERCEL         │
                │                     │
                │  CortexOS Studio    │
                │  Next.js Frontend   │
                │                     │
                │  Public Demo        │
                │  Trace Replay       │
                │  Benchmark Viewer   │
                │  System Explorer    │
                └──────────┬──────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
      REPLAY / DEMO MODE          OPTIONAL LIVE MODE
              │                         │
              ▼                         ▼
    Real Recorded Execution       Compatible Public API
           Traces                 if ₹0 deployment is
                                      feasible
                                        │
                                        ▼
                            ┌────────────────────────┐
                            │ FULL CORTEXOS RUNTIME  │
                            │                        │
                            │ Docker Compose         │
                            │ FastAPI                │
                            │ Workers                │
                            │ PostgreSQL + pgvector  │
                            │ Ollama                 │
                            │ Local Models           │
                            │ Benchmark Engine       │
                            └────────────────────────┘
```

### Deployment Modes

CortexOS should eventually support three explicit operating modes.

#### MODE 1 — Public Demo Mode

Runs through the Vercel deployment.

Purpose:

* recruiter demonstrations,
* public project exploration,
* frontend evaluation,
* architecture exploration,
* execution visualization.

This mode may use real execution traces generated by the full CortexOS runtime and exported as replayable artifacts.

The interface must clearly distinguish replayed executions from live executions.

No benchmark result may be fabricated.

---

#### MODE 2 — Local Full Runtime Mode

Runs through Docker Compose.

Purpose:

* complete CortexOS functionality,
* local model inference,
* knowledge ingestion,
* repository ingestion,
* context compilation,
* Semantic Virtual Memory,
* benchmarking,
* experimentation,
* model routing,
* research evaluation.

Target developer experience:

```text
git clone
    ↓
configure environment
    ↓
docker compose up
    ↓
full CortexOS runtime available
```

---

#### MODE 3 — Connected Live Mode

A future optional mode.

The Vercel-hosted CortexOS Studio may connect to a running CortexOS runtime.

Possible scenarios:

```text
Vercel Studio
      ↓
Secure Runtime Connection
      ↓
User's Local or Self-Hosted CortexOS Runtime
```

This mode would allow the public-quality Studio interface to visualize real live executions without requiring the full AI infrastructure to run on Vercel.

The exact networking and security architecture for this mode remains unresolved and must not be implemented until properly specified.

---

### Vercel Architecture Rules

Claude must preserve the following rules:

1. The Next.js frontend must be designed for Vercel deployment.

2. The complete CortexOS runtime must not depend on Vercel.

3. Local Docker execution must remain the authoritative full-system execution path.

4. Public demonstrations must remain functional even when no live AI runtime is connected.

5. Replay data must originate from real CortexOS executions.

6. Replayed and live executions must be visibly distinguishable.

7. The public frontend must not expose secrets, model credentials, private repository data, or internal runtime configuration.

8. Vercel-specific architecture must remain isolated from the model-agnostic CortexOS runtime.

9. The project must not introduce mandatory paid Vercel services.

10. If a feature cannot operate reliably within the zero-cost Vercel deployment path, it must remain available through the Dockerized full runtime rather than being removed from CortexOS.

## 10. Important cost principle

“Zero cost” means zero mandatory monetary expenditure, not zero hardware usage.

The student may use an existing personal machine for:
- local inference,
- benchmarking,
- Docker,
- model execution.

The project should still define minimum hardware expectations and CPU-only fallback behavior.

---

## 11. Model strategy remains open

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
