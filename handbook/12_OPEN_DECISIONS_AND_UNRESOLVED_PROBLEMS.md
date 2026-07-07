# PART 12 — OPEN DECISIONS AND UNRESOLVED PROBLEMS

The concept is locked, but many critical implementation decisions are not.

## A. Product definition
Need to decide:
- exact primary user,
- exact first use case,
- exact MVP,
- explicit non-goals,
- whether CortexOS is primarily SDK, proxy, runtime, platform, or combination,
- first end-to-end demo scenario.

## B. Research thesis
Need:
- formal primary hypothesis,
- secondary hypotheses,
- novelty claims,
- original vs adapted ideas,
- realistic proof boundaries,
- claims that must not be made,
- research success criteria.

## C. System boundaries
Need to define:
- what enters CortexOS,
- what exits,
- what CortexOS owns,
- what the application owns,
- what the model owns,
- what the knowledge layer owns,
- trust boundaries.

## D. MVP scope
Need formal division:
- MVP,
- V1,
- V2,
- Research Track,
- Experimental Track.

## E. Docker architecture
Need:
- exact containers,
- responsibilities,
- network topology,
- volumes,
- health checks,
- startup sequence,
- dev compose,
- production compose,
- CPU/RAM requirements,
- model runtime strategy,
- image-size strategy.

## ## F. Vercel Public Deployment Architecture

The public frontend deployment target is now locked as Vercel.

The following remain unresolved:

* exact Vercel project structure,
* Next.js rendering strategy,
* public demo data architecture,
* execution-trace storage format,
* trace delivery strategy,
* static versus dynamic benchmark data,
* lightweight API requirements,
* replay engine architecture,
* live execution streaming architecture,
* secure connection to an external CortexOS runtime,
* authentication requirements,
* public rate limiting,
* deployment environment variables,
* demo fallback behavior,
* offline runtime behavior,
* and the exact boundary between Vercel and the Dockerized runtime.

The final architecture must support:

```text
VERCEL
Public CortexOS Studio
Recruitment Demo
Execution Replay
Benchmark Exploration

+

DOCKER
Complete CortexOS Runtime
Local AI
PostgreSQL
Workers
Ingestion
Full Benchmarks
Research Experiments
```

## G. Model strategy
Need:
- embedding model,
- task model,
- reasoning model,
- evaluator model,
- CPU-compatible set,
- routing rules,
- abstraction interface.

## H. Knowledge architecture
Need:
- parsing strategy,
- segmentation,
- semantic artifact schema,
- Semantic IR schema,
- relationships,
- embeddings,
- versioning,
- provenance,
- contradiction handling.

## I. Context Compiler algorithms
Need exact algorithms for:
- requirement matching,
- necessity scoring,
- redundancy detection,
- contradiction resolution,
- compression,
- representation selection,
- dependency preservation,
- token packing.

## J. Semantic Virtual Memory
Need exact definitions for:
- semantic page,
- page size,
- page identity,
- addressing,
- states,
- fault detection,
- replacement,
- eviction,
- pinning,
- prefetch,
- invalidation,
- memory pressure.

## K. Sufficiency and confidence
Need to determine:
- how sufficiency is measured,
- how confidence is calibrated,
- hallucination risk,
- expansion conditions,
- model-switch conditions,
- stop conditions.

## L. Quality evaluation
Need:
- datasets,
- ground truth,
- human evaluation,
- judge-model limitations,
- reproducibility methodology.

## M. Frontend specification
Need:
- complete IA,
- every screen,
- every panel,
- every interaction,
- runtime states,
- mobile strategy,
- accessibility,
- motion spec,
- design tokens,
- component architecture.

## N. API and SDK
Need:
- public API,
- SDK language,
- integration experience,
- request format,
- streaming protocol,
- trace format,
- error model,
- authentication.

## O. Security
Need:
- prompt injection defense,
- malicious document handling,
- repository privacy,
- data isolation,
- secrets,
- container security,
- abuse prevention.

## P. Failure handling
Need behavior for:
- model failure,
- retrieval failure,
- compiler failure,
- database failure,
- corrupt semantic page,
- persistent low confidence,
- budget overrun,
- worker crash.

## Q. Benchmark design
Need:
- fair baseline implementations,
- datasets,
- experiment count,
- statistics,
- ablations,
- hardware reporting,
- reproducibility.

## R. Repository and specification system
Need:
- repository structure,
- documentation hierarchy,
- spec numbering,
- ADRs,
- implementation plans,
- test plans,
- benchmark records,
- experiment records.

---

# Highest-priority unresolved decisions

Before architecture implementation, resolve:

1. Primary user
2. First use case
3. MVP boundary
4. Product surface: SDK/proxy/runtime/platform
5. Formal research hypothesis
6. Semantic page definition
7. Sufficiency strategy
8. Zero-cost public demo architecture
9. Model portfolio
10. Benchmark suite

These decisions have cascading impact on the entire project.
