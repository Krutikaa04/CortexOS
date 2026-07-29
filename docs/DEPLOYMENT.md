# Deployment

CortexOS runs the same codebase locally and in the cloud — only configuration
differs. This guide covers the two supported topologies.

## Topology

```text
Vercel (Studio)  ──▶  Render / container host (API + worker)  ──▶  managed PostgreSQL (pgvector)
                                     │
                                     └──▶  Ollama-compatible model endpoint
```

The model runtime (Ollama) is **not** deployed to Render — point
`CORTEX_MODEL_BASE_URL` at an Ollama reachable from the backend (a tunnelled
local machine, a GPU VM, or any host exposing the Ollama API).

---

## 1. Local Docker (development / self-host)

```bash
cp .env.example .env      # set CORTEX_DB_PASSWORD
docker compose up         # db · model · migrate · api · 2 workers
```

Services: `cortex-db` (Postgres+pgvector), `cortex-model` (Ollama, auto-pulls
models), `cortex-migrate` (runs `alembic upgrade head`), `cortex-api`,
`cortex-worker` (ingestion), `cortex-worker-benchmark`. Add
`-f docker-compose.dev.yml` for hot reload + host-mapped DB/model + Studio.

Run Studio separately (or via the dev compose): `cd studio && npm install && npm run dev`.

---

## 2. Cloud (Vercel + Render + managed Postgres)

The repository ships a Render blueprint: [`render.yaml`](../render.yaml)
(managed Postgres + web API + background worker, one Docker image).

### Database
Any managed PostgreSQL with the `vector` extension (Render Postgres, Neon,
Supabase). Enable it once: `CREATE EXTENSION IF NOT EXISTS vector;` (migrations
also do this). Use the full connection string as `CORTEX_DB_URL` — a
`postgres://…?sslmode=require` string is normalized to asyncpg and TLS is
applied automatically.

### Migrations
Run once per deploy against the database:
```bash
cd api && alembic upgrade head      # or the Render preDeployCommand in render.yaml
```
No local alembic? Use Docker: `docker compose run --rm --no-deps -e CORTEX_DB_URL=<url> cortex-migrate`.

### Backend API (Render Web Service, Docker)
- Root directory `api`, runtime Docker, health check path `/health/live`.
- Env: `CORTEX_ENV=production`, `CORTEX_DB_URL`, `CORTEX_MODEL_BASE_URL`,
  `CORTEX_ALLOWED_ORIGINS` (the Vercel URL), optional `CORTEX_API_TOKEN`,
  `CORTEX_GIT_TOKEN`.

### Worker (Render Background Worker, Docker)
- Same image; start command `python -m cortex.worker`.
- Env: same DB + model config, `CORTEX_WORKER_KINDS=ingest_source,run_benchmark`,
  `CORTEX_INGEST_DIR=/data/ingest` (attach a disk), `CORTEX_INGEST_CLEANUP=true`
  on ephemeral disks.
- Note: Render has no free worker tier; a zero-cost alternative is to run the
  worker on a machine that also hosts Ollama.

### Frontend (Vercel)
- Import the repo, root directory `studio`, framework Next.js (auto).
- Env: `NEXT_PUBLIC_CORTEX_API_URL=https://<your-api-host>` (no trailing slash).

---

## Environment variables

See [`.env.example`](../.env.example) for the complete, commented list. Grouped:
database (`CORTEX_DB_URL`, `CORTEX_DB_SSL`, pool sizes), model provider
(`CORTEX_MODEL_PROVIDER`, `CORTEX_MODEL_BASE_URL`, timeouts/retries, model
names), runtime (`CORTEX_ENV`, `CORTEX_LOG_LEVEL`, `CORTEX_API_TOKEN`,
`CORTEX_ALLOWED_ORIGINS`, `CORTEX_GIT_TOKEN`), worker/storage
(`CORTEX_WORKER_KINDS`, `CORTEX_INGEST_DIR`, `CORTEX_INGEST_CLEANUP`), and the
frontend `NEXT_PUBLIC_CORTEX_API_URL`.

---

## Production checklist

- [ ] `CORTEX_ENV=production`.
- [ ] `CORTEX_DB_URL` points at managed Postgres with `pgvector`; migrations applied to `0005`.
- [ ] `CORTEX_ALLOWED_ORIGINS` = exact Studio origin(s).
- [ ] `CORTEX_API_TOKEN` set (and Studio configured to send it) if the API must be private.
- [ ] `CORTEX_MODEL_BASE_URL` reachable from **both** API and worker.
- [ ] `CORTEX_GIT_TOKEN` set if cloning private repositories.
- [ ] Worker running and heartbeating (`/health` shows `worker: alive`).
- [ ] `/health` returns `ready: true`; `/health/live` used for the platform probe.
- [ ] Ingest workspace on a persistent disk, or `CORTEX_INGEST_CLEANUP=true` on ephemeral storage.
- [ ] CI green on the deployed commit.
