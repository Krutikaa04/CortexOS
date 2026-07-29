# Changelog

All notable changes to this project are documented here. This project adheres
to [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026

First public release. CortexOS is a repository-grounded AI engineering
intelligence platform, running fully local and zero-cost on Ollama and
deployable to the cloud by configuration.

### Added
- **Repository intelligence core** — knowledge graph of semantic artifacts +
  typed edges; adaptive context compiler; inference budget controller;
  semantic virtual memory; hybrid retrieval; paired RAG baseline + benchmark
  harness.
- **Repository chat** — persistent, repo-scoped conversations (create / switch /
  rename / delete), evidence-backed answers, live Server-Sent-Events streaming
  of pipeline stages.
- **Cross-language graph** — Python and JavaScript/TypeScript (incl. React/
  Next.js), with `tsconfig`/`jsconfig` baseUrl + paths alias resolution and
  monorepo scoping.
- **Change Impact Guard v2** — diff/GitHub-PR impact reports with blast radius,
  per-dimension impact, dependency-chain evidence, structured confidence,
  recommended tests, follow-up suggestions, persistence, and revision-over-
  revision comparison.
- **Engineering intelligence** — dead-code detection, circular-dependency
  detection, repository insights (hotspots, coupling, large modules,
  architecture layers), and request-flow tracing — all deterministic, evidence
  backed, zero model calls.
- **Model provider abstraction** — Ollama default; streaming generation support.
- **Cloud readiness** — env-driven config, managed-Postgres URL normalization +
  TLS, `render.yaml` blueprint, Vercel frontend support.
- **Production hardening** — bearer-token auth gate, repository-URI/ref
  validation (argument-injection / `file://` / traversal protection), structured
  request logging, richer `/health` + `/health/live`, graceful shutdown, worker
  heartbeat, orphaned-execution recovery, GitHub Actions CI.
- **Documentation** — README, architecture, API, deployment, contributing,
  demo, and portfolio docs.

### Notes
- No performance claims are published until the benchmark harness produces
  numbers on a given repository + model pair; the harness measures token
  reduction, model-call count, and latency versus the fixed-top-K baseline.
