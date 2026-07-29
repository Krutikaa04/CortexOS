# Contributing to CortexOS

Thanks for your interest! This guide gets you productive quickly.

## Local setup

Prerequisites: Docker, Python 3.12, Node 22.

```bash
git clone https://github.com/Krutikaa04/CortexOS.git
cd CortexOS
cp .env.example .env                 # set CORTEX_DB_PASSWORD

# full stack (hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# backend tooling on the host
cd api && pip install -e ".[dev]"

# frontend tooling on the host
cd studio && npm install
```

## Running tests & checks

Everything CI runs, you can run locally:

```bash
# backend
cd api
ruff check cortex tests        # lint
python -m pytest -q            # unit tests

# frontend
cd studio
npx tsc --noEmit               # type check
npx next build                 # build verification
```

Please keep the backend **lint-clean** and all tests green before opening a PR.
Add or update tests for any behavior change.

## Coding conventions

- **Python:** ruff-enforced (pyflakes + real-error rules), line length 100,
  target 3.12. Prefer async SQLAlchemy and parameterized SQL. Keep the
  deterministic-vs-inference boundary explicit — no LLM call should decide
  whether to make an LLM call.
- **TypeScript/React:** strict TypeScript, Tailwind for styling, follow the
  existing component patterns in `studio/components`. Keep the design language
  consistent — no visual redesigns in feature PRs.
- **Comments** explain *why*, not *what*. Match the density of the surrounding
  code.
- **Migrations:** every schema change is an Alembic migration in
  `api/alembic/versions`, numbered sequentially, with a matching model in
  `cortex/schema.py`.

## Branch strategy

- `master` is the release branch; keep it green.
- Branch per change: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
- Rebase or merge `master` before requesting review.

## Pull request process

1. Ensure lint, tests, type check, and build all pass locally.
2. Keep PRs focused; describe the change, the reasoning, and how you validated it.
3. CI (`.github/workflows/ci.yml`) must be green — it runs lint, tests, both
   builds, and a Docker build.
4. Update docs (`README.md`, `docs/`) when behavior or endpoints change.

## Reporting issues

Use the issue templates under `.github/ISSUE_TEMPLATE`. Include reproduction
steps, expected vs. actual behavior, and environment details for bugs.
