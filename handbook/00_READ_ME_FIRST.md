# CORTEXOS — CLAUDE MASTER CONTEXT PACK
## Read this file first

This context pack is the authoritative handoff for continuing the design and eventual implementation of **CortexOS**.

Claude must treat the documents in this pack as cumulative. Read them in numerical order before proposing architecture, writing specifications, or implementing code.

## Project status

CortexOS is currently in the **pre-implementation definition and specification phase**.

The project idea is locked.

The following constraints are locked and must not be weakened:

1. **Project name:** CortexOS
2. **Domain:** Generative AI infrastructure
3. **Core problem:** LLM systems waste tokens and compute by repeatedly sending unnecessary context and over-provisioning inference resources.
4. **Core thesis:** Give each task only the minimum sufficient context and computational resources needed to satisfy a target quality level.
5. **Signature innovation:** Semantic Virtual Memory
6. **Second signature innovation:** Context Compiler
7. **Product form:** Model-agnostic adaptive inference runtime with a premium visual control and observability frontend called CortexOS Studio.
8. **Deployment:** Docker-first.
9. **Public Frontend Deployment:** CortexOS Studio must be designed and deployed on Vercel using the zero-cost deployment path available to the student project.
10. **Deployment Architecture:** Vercel is the required public deployment target for the CortexOS Studio frontend and public demonstration experience. The complete CortexOS AI runtime must remain Docker-first and locally executable.
11. **Hybrid Deployment Principle:** The architecture must explicitly separate:
* the Vercel-hosted public CortexOS Studio,
* lightweight public-facing endpoints that are technically suitable for the Vercel environment,
* replayable traces and benchmark demonstrations,
* and the full Dockerized CortexOS runtime containing local AI inference, PostgreSQL, workers, ingestion, benchmarking, and model execution.
12. **No Architecture Conflict:** Docker-first and Vercel deployment are complementary requirements. Docker guarantees complete local reproducibility of the full system. Vercel provides the publicly accessible frontend and recruitment demonstration surface.
13. **Cost:** The complete student implementation must be possible at ₹0 mandatory cost.
14. **AI strategy:** Open-source, local-first, no required commercial LLM API.
15. **Evaluation:** Every optimization claim must be benchmarked against a conventional baseline.
16. **Development strategy:** Specification-first. Do not rush into code.
17. **Portfolio standard:** The final result must be strong enough to serve as a serious large-scale Generative AI / systems engineering recruitment project.

## How to use this pack

Read in this order:

1. `00_READ_ME_FIRST.md`
2. `01_PROJECT_VISION_AND_PROBLEM.md`
3. `02_RESEARCH_THESIS_AND_OPTIMIZATION_MODEL.md`
4. `03_CORE_ARCHITECTURE_AND_RUNTIME_FLOW.md`
5. `04_CONTEXT_COMPILER_AND_SEMANTIC_IR.md`
6. `05_SEMANTIC_VIRTUAL_MEMORY.md`
7. `06_ADAPTIVE_INFERENCE_AND_ADVANCED_OPTIMIZATION.md`
8. `07_KNOWLEDGE_INGESTION_AND_DATA_MODEL.md`
9. `08_CORTEXOS_STUDIO_FRONTEND.md`
10. `09_TECH_STACK_DOCKER_AND_ZERO_COST.md`
11. `10_EVALUATION_BENCHMARKS_AND_RESEARCH.md`
12. `11_BUILD_ROADMAP_AND_VERSIONING.md`
13. `12_OPEN_DECISIONS_AND_UNRESOLVED_PROBLEMS.md`
14. `13_CLAUDE_OPERATING_INSTRUCTIONS.md`

## Critical instruction

Do not silently simplify CortexOS into:
- a chatbot,
- a chat-with-PDF application,
- a standard RAG pipeline,
- a prompt compressor,
- a token counter,
- a generic multi-agent framework,
- an API wrapper,
- or a dashboard around an existing model.

The project is intended to be an **adaptive inference runtime**. Context optimization is its kernel, but the long-term architecture optimizes context, model choice, reasoning depth, retrieval, memory, verification, latency, and compute together.

## Current immediate next step

The next major artifact should be:

**CORTEXOS MASTER SPEC 000 — Product Thesis, Research Claims, System Boundaries, Constraints, and Success Metrics**

No implementation should begin until the major unresolved product and system-boundary questions in this pack have been deliberately settled.
