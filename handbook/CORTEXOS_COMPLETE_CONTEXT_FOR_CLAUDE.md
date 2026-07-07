# CORTEXOS — COMPLETE CLAUDE CONTEXT


---

# SOURCE FILE: 00_READ_ME_FIRST.md

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
9. **Cost:** The complete student implementation must be possible at ₹0 mandatory cost.
10. **AI strategy:** Open-source, local-first, no required commercial LLM API.
11. **Evaluation:** Every optimization claim must be benchmarked against a conventional baseline.
12. **Development strategy:** Specification-first. Do not rush into code.
13. **Portfolio standard:** The final result must be strong enough to serve as a serious large-scale Generative AI / systems engineering recruitment project.

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


---

# SOURCE FILE: 01_PROJECT_VISION_AND_PROBLEM.md

# PART 01 — PROJECT VISION AND PROBLEM

## 1. Official project statement

CortexOS is a Docker-first, zero-cost, model-agnostic adaptive inference runtime that attempts to reduce Generative AI resource consumption by dynamically determining, compiling, managing, and allocating the minimum sufficient context and computational resources required for each task while preserving a defined level of answer quality.

Its signature architectural concept is **Semantic Virtual Memory**, which treats the LLM context window as managed working memory and the wider knowledge environment as a virtual semantic address space.

Its signature execution component is the **Context Compiler**, which transforms raw retrieved knowledge into a minimal, high-density, requirement-aware context representation before inference.

Its long-term goal is to evolve from context optimization into complete quality-constrained inference optimization across:
- context,
- models,
- reasoning depth,
- retrieval,
- memory,
- tools,
- verification,
- latency,
- and compute.

The entire system must be developed using open-source technologies, packaged through Docker, and designed so that a student can build, run, evaluate, demonstrate, and deploy the project without mandatory financial expenditure.

---

## 2. Why CortexOS exists

Modern LLM applications frequently waste resources because they repeatedly send large quantities of information that are not necessary for the current task.

Possible available information can include:
- long conversation histories,
- hundreds of documents,
- retrieved chunks,
- previous agent outputs,
- tool results,
- user preferences,
- long-term memories,
- system instructions,
- source code,
- repository history,
- prior execution state.

Example:

```text
Available knowledge:       850,000 tokens
Retrieved context:          18,000 tokens
Actually required:             900 tokens
```

A conventional application may send most or all of the 18,000 retrieved tokens. CortexOS attempts to identify and compile only the approximately 900 tokens actually needed.

The project begins from the observation that **larger context is not automatically better context**.

Excessive context can increase:
- token consumption,
- financial cost,
- latency,
- compute requirements,
- context pollution,
- distraction,
- retrieval noise,
- contradiction exposure,
- and hallucination risk.

---

## 3. Core problem categories

### 3.1 Excessive context

Applications often send:
- entire conversation histories,
- duplicate information,
- outdated facts,
- irrelevant background,
- repeated system state,
- information already known from previous turns,
- full documents when only a claim is required.

### 3.2 Fixed retrieval strategies

Many RAG systems use fixed policies such as:

```text
chunk_size = 500
top_k = 10
```

This is done regardless of whether a task requires 30 tokens, 500 tokens, 5,000 tokens, or a multi-hop dependency chain.

### 3.3 Fixed model usage

Simple factual lookup and complex architectural analysis are often sent to the same model using the same context strategy.

CortexOS rejects this.

A simple task may need:

```text
Small model
+ 50 context tokens
+ R0 reasoning
+ no verification
```

A difficult task may need:

```text
Stronger model
+ 8,000 context tokens
+ R4 reasoning
+ verification
```

### 3.4 Reasoning over-provisioning

Not every task needs:
- multiple reflection rounds,
- multi-agent debate,
- deep planning,
- repeated verification.

Reasoning itself is a resource that must be allocated.

### 3.5 Context is treated as text, not memory

Most applications treat the context window as a container to fill. CortexOS treats it as a scarce managed resource.

The central analogy is:

```text
Traditional computer system      CortexOS

RAM                              LLM context window
Disk storage                     Raw knowledge
Cache                            Semantic cache
Memory pages                     Semantic knowledge pages
Page fault                       Missing required knowledge
Page replacement                 Context eviction
Prefetching                      Predicted context loading
Virtual memory                   Semantic Virtual Memory
```

---

## 4. Product identity

CortexOS is not primarily an end-user chatbot.

It is intended to sit between an application and one or more AI models:

```text
AI Application
      ↓
CortexOS SDK / API / Runtime
      ↓
Context + resource optimization
      ↓
Model runtime
```

The final product may expose:
- runtime APIs,
- an SDK,
- a proxy/gateway,
- a local execution engine,
- an observability studio.

The exact primary product surface is still an open decision and must be resolved in SPEC 000.

---

## 5. Intended users considered so far

Potential users include:
- AI application developers,
- AI infrastructure engineers,
- teams building RAG systems,
- agent developers,
- researchers,
- students learning inference behavior.

The exact primary user is not yet locked.

---

## 6. Intended use cases considered so far

Potential use cases:
- long-running AI conversations,
- document question answering,
- repository question answering,
- enterprise knowledge retrieval,
- multi-agent systems,
- AI research assistants,
- adaptive RAG systems,
- persistent AI memory,
- complex workflow agents.

The first benchmark use case and first end-to-end demo scenario remain unresolved.

---

## 7. What must make this project recruitment-worthy

The project must demonstrate more than LLM API usage.

It should show credible work in:
- Generative AI systems,
- RAG and retrieval,
- information representation,
- graph reasoning,
- adaptive systems,
- systems design,
- scheduling and resource allocation,
- caching,
- memory management,
- evaluation,
- observability,
- data engineering,
- frontend visualization,
- Docker and reproducibility,
- research methodology.

The project should be defensible in interviews through:
- clear architecture,
- measurable claims,
- benchmark evidence,
- design trade-offs,
- failure analysis,
- ablation studies,
- reproducible experiments,
- and a technically impressive demo.


---

# SOURCE FILE: 02_RESEARCH_THESIS_AND_OPTIMIZATION_MODEL.md

# PART 02 — RESEARCH THESIS AND OPTIMIZATION MODEL

## 1. Primary research question

> How can an AI runtime identify and provide the smallest possible amount of context and computation required to preserve a target level of answer quality?

This is the central question around which CortexOS should be designed.

---

## 2. Original narrow objective

The initial idea was to reduce cost by preventing unnecessary context tokens from being sent to an LLM.

The first optimization framing was:

```text
minimize Context Tokens
subject to
Quality(context, task) ≥ Q_required
```

This remains the kernel of CortexOS.

---

## 3. Expanded objective

The project later evolved beyond input token reduction.

The broader objective is:

```text
Minimize:
    token cost
  + compute cost
  + latency
  + retrieval cost
  + tool cost
  + verification cost

Subject to:
    answer quality ≥ required quality threshold
```

The runtime should eventually decide the cheapest combination of:
- context,
- model,
- reasoning depth,
- retrieval depth,
- tools,
- memory,
- verification,
- and escalation.

---

## 4. Information Bottleneck connection

A useful theoretical framing is the Information Bottleneck principle.

Let:
- X = all available knowledge,
- Z = compiled context,
- Y = correct task output.

Conceptually:

```text
maximize I(Z; Y) - β I(Z; X)
```

The practical interpretation is:

> Preserve information necessary for the answer while discarding everything else.

This should be treated as a conceptual research foundation, not as a claim that the initial implementation directly solves mutual-information optimization exactly.

---

## 5. Semantic Density

A proposed project metric is:

```text
Semantic Density =
Task-Relevant Information / Token Count
```

The Context Compiler should prefer information artifacts with high task-relevant utility per token.

A broader context-value concept was discussed:

```text
Context Value =
    Task Relevance
  × Information Necessity
  × Source Reliability
  × Temporal Validity
  × Dependency Importance
  ÷ Token Cost
```

This exact formula is not yet locked. It is a conceptual starting point.

---

## 6. Quality-constrained optimization

CortexOS must not optimize tokens blindly.

A result such as:

```text
90% fewer tokens
40% lower quality
```

is not success.

The meaningful result is closer to:

```text
84.5% fewer tokens
98.7% answer-quality retention
```

The system must explicitly trade resource savings against quality.

---

## 7. Candidate research hypotheses

These are not yet formalized and must be refined in SPEC 000.

Possible primary hypothesis:

> Requirement-aware context compilation can reduce context-token consumption compared with fixed Top-K RAG while retaining a defined proportion of answer quality.

Possible secondary hypotheses:

1. Structured semantic representations can preserve task-relevant information using fewer tokens than raw retrieved chunks.
2. Dynamic context budgets outperform fixed context budgets across heterogeneous task complexity.
3. Semantic Virtual Memory can reduce repeated context transmission in long-running workflows.
4. Confidence-calibrated escalation can reduce average inference resource use without materially reducing task success.
5. Dependency-aware cache invalidation can improve reuse while reducing stale-context errors.
6. Model-context co-optimization can outperform fixed-model execution on total resource cost.

These hypotheses must be made testable and scoped.

---

## 8. Research integrity requirements

CortexOS must not make unsupported claims.

No claim such as:
- “82% cheaper,”
- “faster,”
- “better quality,”
- “reduces hallucination,”
- “more scalable,”

may be stated as fact until supported by actual experiments.

The project must distinguish:
- design intention,
- hypothesis,
- experimental result,
- observed limitation.

---

## 9. Benchmark philosophy

Every major optimization should be compared against a fair baseline.

The initial mandatory baseline is conventional RAG:

```text
Query
  ↓
Embedding search
  ↓
Top-K chunks
  ↓
Prompt construction
  ↓
LLM
  ↓
Answer
```

Later comparisons may include:
- Baseline RAG
- CortexOS Kernel
- CortexOS + Context Compiler
- CortexOS + Semantic Virtual Memory
- CortexOS + Adaptive Runtime
- CortexOS + Learned Policy

This enables ablation studies and prevents the project from becoming a collection of unmeasured features.


---

# SOURCE FILE: 03_CORE_ARCHITECTURE_AND_RUNTIME_FLOW.md

# PART 03 — CORE ARCHITECTURE AND RUNTIME FLOW

## 1. High-level product architecture

```text
┌──────────────────────────────────────────────────────┐
│                   CORTEXOS STUDIO                    │
│ Visual playground • Analytics • Traces • Benchmarks │
├──────────────────────────────────────────────────────┤
│                   CORTEXOS RUNTIME                   │
│ Task Profiler                                        │
│ Requirement Engine                                   │
│ Context Compiler                                     │
│ Semantic Virtual Memory                              │
│ Model Router                                         │
│ Execution + Evaluation                               │
├──────────────────────────────────────────────────────┤
│                    KNOWLEDGE LAYER                   │
│ Raw Docs │ Vector Index │ Graph │ Cache │ Memory     │
└──────────────────────────────────────────────────────┘
```

---

## 2. Target runtime flow

```text
APPLICATION
    │
    ▼
CORTEXOS GATEWAY
    │
    ▼
TASK PROFILER
    │
    ▼
INFORMATION REQUIREMENT GRAPH
    │
    ▼
PREDICTIVE BUDGET ALLOCATOR
    │
    ▼
SEMANTIC MEMORY BUS
    │
    ├── Active Context
    ├── Semantic Cache
    ├── Knowledge Graph / Relationship Store
    ├── Vector Index
    └── Raw Storage
    │
    ▼
CONTEXT COMPILER
    │
    ├── Semantic IR
    ├── Deduplication
    ├── Compression
    └── Dependency preservation
    │
    ▼
CONTEXT UTILITY MODEL
    │
    ▼
SEMANTIC PAGING ENGINE
    │
    ▼
MODEL-CONTEXT CO-OPTIMIZER
    │
    ▼
ADAPTIVE REASONING ENGINE
    │
    ▼
EXECUTION
    │
    ▼
SUFFICIENCY EVALUATOR
    │
    ├── Sufficient → Return
    └── Insufficient → Page fault / escalation
    │
    ▼
COUNTERFACTUAL ANALYZER
    │
    ▼
POLICY LEARNING LOOP
```

The early implementation will not contain every box. This is the long-term architecture.

---

## 3. CortexOS Kernel V1

The first real runtime should contain only five major components:

1. Task Profiler
2. Requirement Generator
3. Hybrid Retriever
4. Context Compiler
5. Sufficiency Evaluator

Flow:

```text
Query
  ↓
Task Profiler
  ↓
Requirement Generator
  ↓
Hybrid Retrieval
  ↓
Context Compiler
  ↓
LLM
  ↓
Sufficiency Evaluator
  ├── sufficient → return
  └── insufficient → expand context
```

This is the first meaningful vertical slice.

---

## 4. Task Profiler

Purpose:
- classify task type,
- estimate complexity,
- estimate knowledge dependence,
- estimate dependency depth,
- estimate ambiguity,
- estimate risk,
- propose a context budget,
- propose reasoning depth,
- propose whether verification is required.

Example profile:

```text
Complexity            0.74
Knowledge dependence  0.91
Reasoning depth       0.43
Temporal sensitivity  0.82
Dependency depth      0.61
Ambiguity              0.32
Risk tolerance         0.10
```

Possible output:

```text
Expected sufficient context: 2,400–3,100 tokens
Expected retrieval depth: 3
Expected reasoning budget: medium
Expected verification: required
```

Initial implementation should use deterministic heuristics. Learned prediction comes later.

---

## 5. Information Requirement Engine

Before retrieval, the system should ask:

> What information must be known to solve this task?

Example query:

```text
Will changing the authentication middleware affect payments?
```

Possible requirement graph:

```text
                ROOT TASK
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
Authentication State         Payment API
        │                       │
        ▼                       ▼
Session Properties       Auth Dependency
        │                       │
        └───────────┬───────────┘
                    ▼
             Dependency Path
```

The distinction is important:

```text
Semantically similar information
≠
Information actually necessary to solve the task
```

---

## 6. Hybrid Retriever

The planned retriever may combine:
- semantic/vector search,
- lexical search,
- graph/relationship expansion,
- metadata filters,
- temporal validity,
- provenance,
- requirement coverage.

The exact retrieval algorithm is unresolved.

---

## 7. Sufficiency Evaluator

The system must determine whether the current context and answer are sufficient.

This is one of the hardest unsolved parts.

Potential signals:
- requirement coverage,
- evidence coverage,
- answer consistency,
- retrieval confidence,
- contradiction presence,
- uncertainty,
- evaluator score,
- task-specific validation.

The exact sufficiency mechanism must be designed carefully. The project must not pretend that model self-confidence alone is reliable.

---

## 8. Execution event model

The frontend requires runtime events such as:

```text
TASK_RECEIVED
TASK_PROFILED
REQUIREMENTS_CREATED
RETRIEVAL_STARTED
CANDIDATE_FOUND
CANDIDATE_REJECTED
CONTEXT_DEDUPLICATED
CONTEXT_COMPRESSED
CONTEXT_COMPILED
MODEL_SELECTED
INFERENCE_STARTED
PAGE_FAULT
PAGE_IN
PAGE_OUT
PREFETCH
EVICT
PIN
INVALIDATE
SUFFICIENCY_CHECKED
ESCALATION_TRIGGERED
EXECUTION_COMPLETED
```

The exact event schema remains to be specified.

---

## 9. Observability principle

Every important runtime decision should be explainable.

For any execution, CortexOS Studio should be able to answer:
- what knowledge was available,
- what was selected,
- what was rejected,
- why it was rejected,
- how many tokens were saved,
- what model was chosen,
- what reasoning tier was used,
- whether escalation occurred,
- whether a page fault occurred,
- how the result compared with baseline.


---

# SOURCE FILE: 04_CONTEXT_COMPILER_AND_SEMANTIC_IR.md

# PART 04 — CONTEXT COMPILER AND SEMANTIC IR

## 1. Purpose

The Context Compiler is one of the two signature systems in CortexOS.

Conventional RAG:

```text
Retrieve chunks
  ↓
Put chunks in prompt
```

CortexOS:

```text
Retrieve candidate knowledge
  ↓
Compile knowledge for the task
  ↓
Send minimum sufficient representation
```

The compiler should transform retrieved knowledge into a high-density, requirement-aware context.

---

## 2. Planned compiler pipeline

```text
Candidate Context
      ↓
1. Normalize
      ↓
2. Match requirements
      ↓
3. Score necessity
      ↓
4. Detect redundancy
      ↓
5. Analyze contradictions
      ↓
6. Select representation
      ↓
7. Compress
      ↓
8. Preserve dependencies
      ↓
9. Pack token budget
      ↓
Compiled Context
```

---

## 3. Example

```text
Candidate context:         23,841 tokens

Rejected as irrelevant:     8,410
Removed as duplicate:       4,930
Replaced by known facts:    3,220
Compressed:                 4,781

Required final context:     2,500
```

The key benchmark is not compression alone. It is compression while preserving answer quality.

---

## 4. Context artifact metadata

A conceptual structure discussed so far:

```text
ContextArtifact {
    id
    source
    rawTokenCount
    compiledTokenCount

    relevanceScore
    necessityScore
    semanticDensity
    reliabilityScore
    temporalValidity

    requirementsSatisfied[]
    dependencies[]

    representationLevel
    rejectionReason
}
```

This schema is not final.

---

## 5. Context utility granularity

CortexOS should eventually move below document-level retrieval:

```text
Document
  ↓
Section
  ↓
Paragraph
  ↓
Sentence
  ↓
Claim
  ↓
Token span
```

Example:

```text
Original passage: 480 tokens

Useful spans:
tokens 43–71
tokens 182–215
tokens 401–438

Compiled context: 96 tokens
```

This idea is called sparse context representation.

---

## 6. Semantic Intermediate Representation

Raw text example:

```text
The authentication service uses JWT access tokens with a validity
period of fifteen minutes. Refresh tokens are stored as hashed
values in PostgreSQL.
```

Possible Semantic IR:

```text
ENTITY AuthService

USES JWT

ACCESS_TOKEN
    ttl = 15m

REFRESH_TOKEN
    storage = PostgreSQL
    representation = hash
```

The runtime can choose among:

```text
L0 — Entity reference
L1 — Atomic fact
L2 — Relationship
L3 — Compressed claim
L4 — Source excerpt
L5 — Full source
```

The guiding rule is:

> Use the cheapest representation capable of satisfying the information requirement.

---

## 7. Dependency preservation

Compression must not destroy information needed to reason across dependencies.

Example:

```text
Auth middleware
  → creates session state
  → payment API reads user_id
  → changing session schema may break payment
```

A naive summary may preserve the entities but lose the causal/dependency path.

Therefore the compiler must preserve:
- critical relationships,
- conditions,
- temporal order,
- negation,
- constraints,
- exceptions,
- provenance.

---

## 8. Contradiction handling

The system may retrieve conflicting information.

Example:
- old architecture document says MongoDB,
- current decision record says PostgreSQL.

The compiler should not simply concatenate both.

It must consider:
- source version,
- temporal validity,
- authority,
- supersession,
- confidence,
- scope.

Exact contradiction-resolution policy remains unresolved.

---

## 9. Context counterfactual analysis

Advanced research feature:

After an answer is produced, remove or alter context components and observe quality changes.

```text
Full context → quality 96%

Remove A → 96%
Remove B → 95%
Remove C → 61%
```

Possible conclusion:
- C is causally important,
- A is likely unnecessary,
- B has low contribution.

This can create training data for a future Context Utility Model.

This is not an MVP feature.

---

## 10. Context provenance

Every compiled artifact should retain enough provenance to answer:
- where did this fact come from,
- what source version produced it,
- what transformation was applied,
- what requirement did it satisfy,
- why was it included,
- why were alternatives rejected.

This powers the Context X-Ray frontend.


---

# SOURCE FILE: 05_SEMANTIC_VIRTUAL_MEMORY.md

# PART 05 — SEMANTIC VIRTUAL MEMORY

## 1. Core idea

Semantic Virtual Memory is the signature architectural concept of CortexOS.

Principle:

> An LLM should not need all available knowledge in its context window, just as a process does not require an entire disk loaded into RAM.

The context window is active working memory. The wider knowledge environment is a virtual semantic address space.

---

## 2. Memory hierarchy

```text
LLM Context Window      = RAM / active memory
Semantic Cache          = cache
Knowledge Graph         = indexed structured storage
Vector Store            = semantic retrieval storage
Raw Documents           = cold storage
```

---

## 3. Memory states

Planned states:

### ACTIVE
Currently required by an execution.

### WARM
Recently relevant or likely to be needed soon.

### COLD
Available through retrieval but not active.

### ARCHIVED
Rarely required.

### INVALID
Stale, contradicted, superseded, or untrustworthy.

---

## 4. Planned operations

```text
PAGE_IN()
PAGE_OUT()
PREFETCH()
EVICT()
PIN()
INVALIDATE()
COMPACT()
```

Meaning:

- PAGE_IN: load information into active context.
- PAGE_OUT: remove information from active context.
- PREFETCH: predict and prepare likely future information.
- EVICT: remove low-value context under pressure.
- PIN: prevent critical information from being removed.
- INVALIDATE: mark knowledge stale or unsafe to reuse.
- COMPACT: merge or compress redundant active knowledge.

---

## 5. Semantic Page Fault

Example:

```text
Model is executing
      ↓
Required information is unavailable
      ↓
Semantic Page Fault
      ↓
Identify missing requirement
      ↓
Locate smallest suitable semantic page
      ↓
Choose representation level
      ↓
Allocate tokens
      ↓
Inject context
      ↓
Continue execution
```

The exact mechanics of “continuing execution” depend on model/runtime capabilities and must be designed realistically.

---

## 6. Semantic address space

A conceptual example:

```text
0x001 → User identity facts
0x002 → Current project architecture
0x003 → Authentication system
0x004 → Database decisions
0x005 → Historical decisions
```

This is a conceptual metaphor. The actual addressing scheme is not yet designed.

Open questions:
- Is a page a claim bundle, entity neighborhood, document segment, dependency subgraph, or adaptive unit?
- Is page size fixed or variable?
- How are pages versioned?
- How are pages shared?
- How are addresses stable across re-ingestion?

---

## 7. Page replacement and value

A conceptual first policy:

```text
Page Value =
    Relevance
  × Predicted Future Utility
  × Dependency Importance
  × Recency
  ÷ Token Size
```

This is not a final formula.

Later policies may be learned.

---

## 8. Advanced OS-inspired features

Potential later features:
- working-set estimation,
- page replacement algorithms,
- predictive prefetching,
- dirty-page tracking,
- shared pages across agents,
- copy-on-write context for branching agents,
- memory pressure management,
- context fragmentation measurement,
- learned page replacement.

These features should only be implemented if they support the core thesis and can be evaluated.

---

## 9. Semantic memory interface concept

Example Studio view:

```text
SEMANTIC ADDRESS SPACE                     72% PRESSURE

ACTIVE
0x001 Authentication State    PINNED
0x002 Payment Dependencies    ACTIVE
0x003 Session Schema          ACTIVE

WARM
0x004 User Permissions        PREFETCHED
0x005 API Architecture        WARM

COLD
0x006 Legacy Authentication   EVICTED
```

Runtime events:

```text
14:32:01.283  PAGE_IN      payment.dependencies
14:32:01.291  PIN          auth.session_state
14:32:01.304  EVICT        legacy.auth_v1
14:32:01.419  PAGE_FAULT   role.permissions
14:32:01.437  RESOLVED     18ms
```

---

## 10. Important caution

The OS analogy must not become empty branding.

The implementation must define:
- what a semantic page is,
- how page faults are detected,
- how pages are selected,
- what active memory means for stateless model calls,
- how memory state changes are persisted,
- how benefits are benchmarked.

If those definitions are absent, “Semantic Virtual Memory” becomes only a metaphor. The project must make it operational.


---

# SOURCE FILE: 06_ADAPTIVE_INFERENCE_AND_ADVANCED_OPTIMIZATION.md

# PART 06 — ADAPTIVE INFERENCE AND ADVANCED OPTIMIZATION

## 1. Predictive context allocation

Before retrieval, CortexOS should eventually estimate how much context a task will require.

Inputs may include:
- task type,
- complexity,
- knowledge dependence,
- ambiguity,
- dependency depth,
- required confidence,
- model characteristics,
- historical executions.

Outputs may include:
- expected context range,
- retrieval depth,
- reasoning tier,
- verification requirement.

Initial version: heuristics.
Later version: learned prediction.

---

## 2. Progressive context loading

Do not send all potentially useful context immediately.

```text
Level 0 — Query only
  ↓ insufficient
Level 1 — Core facts
  ↓ insufficient
Level 2 — Supporting evidence
  ↓ insufficient
Level 3 — Dependency context
  ↓ insufficient
Level 4 — Full source material
```

Stop as soon as sufficient evidence exists.

Critical trade-off:

> Multiple inference calls may cost more than sending extra context initially.

Therefore CortexOS needs an expansion cost model.

---

## 3. Adaptive reasoning depth

Planned tiers:

```text
R0 — Direct execution
R1 — Short reasoning
R2 — Structured reasoning
R3 — Multi-step planning
R4 — Verification loop
R5 — Multi-agent deliberation
```

The runtime should prevent reasoning over-provisioning.

---

## 4. Confidence-calibrated escalation

Start with the cheapest reasonable plan.

Example:

```text
Small model + minimal context
      ↓
Confidence / sufficiency adequate
      ↓
Return
```

If inadequate:

```text
Add evidence
  ↓
Improve retrieval
  ↓
Increase reasoning depth
  ↓
Switch to stronger model
  ↓
Parallel verification
  ↓
Human review
```

Proposed escalation ladder:

```text
E0 Minimal context
E1 Additional evidence
E2 Better retrieval
E3 Deeper reasoning
E4 Stronger model
E5 Parallel verification
E6 Human review
```

The exact confidence model remains unresolved.

---

## 5. Model-context co-optimization

The same task can have multiple execution plans.

```text
Plan A:
Strong model
500 context tokens

Plan B:
Small model
2,000 context tokens
```

The smaller model may still be cheaper overall.

CortexOS should eventually optimize the pair:

```text
(model choice, context plan)
```

rather than choosing each independently.

---

## 6. Semantic context cache

Equivalent questions should map to canonical information requirements.

Examples:

```text
What database are we using?
Which DB did we choose?
Is this system running PostgreSQL?
```

Possible canonical requirement:

```text
project.database.current
```

Cache entry concept:

```text
Requirement: project.database.current
Resolved value: PostgreSQL
Confidence: 0.99
Evidence: architecture/database.md
Invalidation trigger: database architecture dependency changes
```

The key innovation is dependency-aware invalidation, not simple TTL expiry.

---

## 7. Context Delta Engine

Long conversations repeatedly resend unchanged information.

Concept:

```text
Previous Context State
+ New Information Delta
+ Current Requirements
= Next Required Context State
```

The system should understand:
- what was previously active,
- what changed,
- what remains relevant,
- what expired,
- what can be removed,
- what can be reused.

Technical feasibility depends on model APIs and local inference behavior.

---

## 8. Context prefetching

If the current path is:

```text
Authentication
  ↓
Session validation
  ↓
Authorization
```

the runtime may predict that role permissions are needed next.

Prefetch only when:

```text
Probability of future use
× Expected utility
> Prefetch cost
```

This is a later feature.

---

## 9. Speculative context execution

When uncertain which context plan is best:

```text
Branch A — database context only
Branch B — authentication context only
Branch C — combined context
```

Cheap evaluation can reject weak branches before expensive reasoning.

This is inspired by speculative execution.

---

## 10. Learned context policy

State may include:
- task features,
- available knowledge,
- current context,
- current model,
- token budget,
- confidence,
- previous retrieval results.

Actions may include:
- RETRIEVE,
- EXPAND,
- COMPRESS,
- REMOVE,
- EVICT,
- PREFETCH,
- CHANGE_MODEL,
- INCREASE_REASONING,
- VERIFY,
- STOP.

Reward concept:

```text
+ answer quality
- token cost
- latency
- compute cost
- unnecessary retrieval
- failed escalations
```

Planned progression:

```text
V1: deterministic heuristics
V2: statistical policies
V3: contextual bandits
V4: offline policy learning
V5: reinforcement learning only if experimentally justified
```

Do not start with RL.

---

## 11. Cross-request context deduplication

Equivalent information requirements across users or executions may reuse canonical semantic artifacts.

Concept:

```text
Knowledge compiled once
      ↓
Canonical Semantic Artifact
      ↓
Reused across equivalent executions
```

This must respect isolation, privacy, versioning, and provenance.

---

## 12. Context causality

Most systems ask:

> Is this chunk similar to the query?

CortexOS eventually wants to ask:

> Did this information materially affect correctness?

This is the motivation behind counterfactual context ablation and utility learning.


---

# SOURCE FILE: 07_KNOWLEDGE_INGESTION_AND_DATA_MODEL.md

# PART 07 — KNOWLEDGE INGESTION AND DATA MODEL

## 1. Initial supported inputs

Planned initial inputs:
- plain text,
- Markdown,
- PDF,
- source code,
- Git repositories.

---

## 2. Ingestion pipeline

```text
Source
  ↓
Parser
  ↓
Structural Segmentation
  ↓
Entity Extraction
  ↓
Claim Extraction
  ↓
Relationship Extraction
  ↓
Embedding Generation
  ↓
Semantic IR Creation
  ↓
Storage
```

---

## 3. Avoid naive fixed-size chunking

The project should not depend exclusively on arbitrary 500-token windows.

Document structure concept:

```text
Document
├── Section
│   ├── Claim
│   ├── Claim
│   └── Relationship
└── Section
```

Repository structure concept:

```text
Repository
├── Module
│   ├── Class
│   │   ├── Method
│   │   └── Dependency
│   └── Function
└── API
```

The system should reason over information units and relationships, not only chunks.

---

## 4. Planned storage direction

Current preferred stack:

```text
PostgreSQL
+
pgvector
```

Responsibilities:
- application state,
- execution traces,
- benchmark results,
- vector embeddings,
- knowledge metadata,
- semantic artifacts,
- memory state,
- graph-like relationships.

A separate graph database should not be added initially unless benchmarks prove it necessary.

---

## 5. Knowledge representation requirements

The data model must eventually support:
- source identity,
- source version,
- structural location,
- raw content,
- extracted claims,
- entities,
- relationships,
- embeddings,
- provenance,
- temporal validity,
- confidence,
- supersession,
- contradiction links,
- semantic representation level,
- token counts,
- requirement coverage.

Exact schemas remain open.

---

## 6. Versioning and invalidation

CortexOS needs to know when knowledge changes.

Example:
- source file modified,
- architecture decision superseded,
- repository commit changes a dependency,
- user preference changes,
- document removed.

This matters for:
- semantic cache invalidation,
- page invalidation,
- provenance,
- benchmark reproducibility.

---

## 7. Repository ingestion opportunity

Repository QA is a particularly strong possible first use case because it naturally contains:
- dependency graphs,
- structured entities,
- version history,
- multi-hop questions,
- measurable context waste.

However, this is not yet locked as the first use case.

---

## 8. Open design questions

Still unresolved:
- parser libraries,
- code AST strategy,
- PDF extraction strategy,
- claim extraction method,
- entity normalization,
- relationship schema,
- graph traversal strategy,
- embedding model,
- embedding dimensionality,
- re-indexing,
- source versioning,
- contradiction handling,
- deletion semantics.


---

# SOURCE FILE: 08_CORTEXOS_STUDIO_FRONTEND.md

# PART 08 — CORTEXOS STUDIO FRONTEND

## 1. Frontend purpose

The frontend is not decoration.

CortexOS performs invisible backend operations. CortexOS Studio must make those operations observable, understandable, and impressive.

The user should be able to see:
- what knowledge was available,
- what information was selected,
- what was rejected,
- why it was rejected,
- how many tokens were saved,
- what memory pages were active,
- when page faults occurred,
- what model was selected,
- how execution escalated,
- how CortexOS compared with baseline RAG.

---

## 2. Visual identity

Avoid:
- generic purple AI gradients,
- floating chatbot layouts,
- robot illustrations,
- excessive glassmorphism,
- generic SaaS dashboards.

Target feeling:

```text
AI Runtime Profiler
+
Operating System Monitor
+
Distributed Tracing Platform
+
Database Observability Tool
+
Developer Infrastructure Product
```

Visual direction:
- dark graphite background,
- near-black workspace,
- fine technical grid,
- precise typography,
- monospace telemetry,
- electric cyan for active context,
- amber for token pressure,
- red for rejected or failed operations,
- green for successful optimization,
- precise purposeful motion.

Color details are conceptual and should later become formal design tokens.

---

## 3. Planned information architecture

```text
CortexOS Studio
├── Command Center
├── Inference Playground
├── Context X-Ray
├── Semantic Virtual Memory
├── Execution Traces
├── Benchmark Lab
├── Knowledge Explorer
├── Model Registry
├── Policy Lab
└── System Settings
```

---

## 4. Command Center

The first screen recruiters see.

Metrics considered:
- raw tokens processed,
- tokens actually used,
- token reduction,
- quality retention,
- total executions,
- live runtime operations,
- memory pressure,
- page faults,
- cache performance,
- recent executions.

Concept:

```text
CORTEXOS                                      SYSTEM: ONLINE

ADAPTIVE INFERENCE RUNTIME

18.4M        4.2M          77.1%          98.2%
Raw Tokens   Tokens Used   Reduction      Quality Retained

TOKEN CONSUMPTION            LIVE RUNTIME
Baseline ━━━━━━━━━━━          TASK_9481 COMPILING
Cortex   ━━━                  TASK_9480 COMPLETE
                              TASK_9479 PAGE_FAULT
```

The numbers should animate based on actual or replayed execution events.

---

## 5. Inference Playground

Primary demo screen.

Three-column concept:

```text
┌─────────────────┬───────────────────────────┬─────────────────┐
│ KNOWLEDGE       │ EXECUTION CANVAS          │ INSPECTOR       │
│ Sources         │ User Query                │ Tokens          │
│ Documents       │ ↓                         │ Latency         │
│ Memories        │ Task Profile              │ Quality         │
│ Cache           │ ↓                         │ Model           │
│                 │ Requirement Graph         │ Context         │
│                 │ ↓                         │ Decisions       │
│                 │ Context Compiler          │                 │
│                 │ ↓                         │                 │
│                 │ Model                     │                 │
│                 │ ↓                         │                 │
│                 │ Answer                    │                 │
└─────────────────┴───────────────────────────┴─────────────────┘
```

Main visual sequence:

```text
47 candidate artifacts
      ↓
31 rejected
      ↓
9 deduplicated
      ↓
4 compressed
      ↓
3 compiled

23,841 available tokens
      ↓
1,842 allocated tokens

92.3% REDUCTION
```

---

## 6. Task Profile visualization

Example:

```text
TASK PROFILE

Complexity         ███████░░ 0.76
Knowledge Need     █████████ 0.94
Dependency Depth   ██████░░░ 0.68
Risk               ███████░░ 0.71
```

---

## 7. Requirement Graph visualization

Example:

```text
              [ROOT QUESTION]
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
[Authentication State]    [Payment API]
          │                     │
          └──────────┬──────────┘
                     ▼
            [Dependency Path]
```

Nodes should appear progressively and correspond to real runtime events.

---

## 8. Context X-Ray

Purpose: explain every context decision.

Concept:

```text
RAW KNOWLEDGE                     COMPILED CONTEXT

auth-middleware.ts  ────────────→ AUTH_STATE
session-service.ts  ────────────→ SESSION_SCHEMA
old-auth-docs.md    ───── X
README.md           ───── X
payment-route.ts    ────────────→ PAYMENT_DEP
architecture.md     ────────────→ ARCH_DECISION
```

Rejected artifact inspector:

```text
REJECTION REASON

README.md / lines 142–190
Tokens: 483

Rejected because:
- low task necessity
- duplicated by architecture.md
- semantic density: 0.14
- no dependency path to target requirement

Estimated tokens saved: 483
```

---

## 9. Semantic Virtual Memory screen

Concept:

```text
SEMANTIC ADDRESS SPACE                     72% PRESSURE

ACTIVE MEMORY
0x001 Authentication State     PINNED
0x002 Payment Dependencies     ACTIVE
0x003 Session Schema           ACTIVE

WARM MEMORY
0x004 User Permissions         PREFETCHED
0x005 API Architecture         WARM

COLD MEMORY
0x006 Legacy Authentication    EVICTED
```

Runtime event stream:

```text
14:32:01.283 PAGE_IN    payment.dependencies
14:32:01.291 PIN        auth.session_state
14:32:01.304 EVICT      legacy.auth_v1
14:32:01.419 PAGE_FAULT role.permissions
14:32:01.437 RESOLVED   18ms
```

This should be one of the most memorable parts of the project.

---

## 10. Benchmark Lab

Dataset categories considered:
- long conversations,
- document QA,
- repository QA,
- multi-hop reasoning,
- custom datasets.

Comparison modes:

```text
Baseline RAG
vs CortexOS Kernel
vs CortexOS + Context Compiler
vs CortexOS + Semantic Virtual Memory
vs CortexOS + Adaptive Runtime
vs CortexOS + Learned Policy
```

Visualizations:
- token reduction,
- quality retention,
- latency,
- context precision,
- hallucination rate,
- page fault rate,
- cache hit rate,
- semantic density.

---

## 11. Frontend technical stack

Planned:
- Next.js,
- TypeScript,
- Tailwind CSS,
- Framer Motion,
- React Flow,
- D3.js where advanced custom visualization is needed,
- Recharts for standard charts.

---

## 12. Frontend development strategy

Build the frontend shell early using typed mock events.

This allows:
- visual design to progress before the AI runtime is complete,
- frontend and backend work to remain decoupled,
- runtime event contracts to be defined early,
- the public demo to support replaying real recorded traces later.

The final frontend must not fake benchmark claims. Replayed traces must come from actual executions and be represented honestly.


---

# SOURCE FILE: 09_TECH_STACK_DOCKER_AND_ZERO_COST.md

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


---

# SOURCE FILE: 10_EVALUATION_BENCHMARKS_AND_RESEARCH.md

# PART 10 — EVALUATION, BENCHMARKS, AND RESEARCH

## 1. Mandatory baseline

Before CortexOS claims improvement, build the system it must beat:

```text
Query
  ↓
Embedding Search
  ↓
Top-K Retrieval
  ↓
Prompt Construction
  ↓
LLM
  ↓
Answer
```

Store comparable data for baseline and CortexOS.

---

## 2. Per-run metrics discussed

### Baseline
- input tokens,
- output tokens,
- total context,
- retrieved chunks,
- latency,
- answer,
- quality score,
- estimated cost.

### CortexOS
- input tokens,
- output tokens,
- compiled context,
- rejected context,
- page faults,
- model selected,
- latency,
- answer,
- quality score,
- estimated cost,
- cache hits,
- expansion count.

---

## 3. Efficiency metrics

- token reduction percentage,
- input-token reduction,
- output-token reduction,
- context compression ratio,
- context utilization,
- semantic density,
- cache hit rate,
- retrieval efficiency.

---

## 4. Quality metrics

- answer accuracy,
- quality retention,
- faithfulness,
- evidence coverage,
- hallucination rate,
- requirement satisfaction.

---

## 5. Runtime metrics

- latency,
- time to first token,
- total execution time,
- retrieval time,
- compilation time,
- page-fault resolution time.

---

## 6. Memory metrics

- active context size,
- memory pressure,
- page-fault rate,
- eviction rate,
- prefetch accuracy,
- invalidation rate.

---

## 7. Adaptive runtime metrics

- escalation frequency,
- unnecessary escalations,
- model-routing accuracy,
- budget-prediction error,
- reasoning over-provisioning.

---

## 8. Example desired report format

Illustrative only:

```text
BASELINE RAG

Input Tokens:       18,420
Quality:            91.2%
Latency:            4.8s

CORTEXOS

Input Tokens:        3,140
Quality:            92.1%
Latency:            3.2s

RESULT

Token Reduction:    82.9%
Quality Change:      +0.9%
```

Do not use these numbers as actual results.

---

## 9. Benchmark categories considered

- long conversations,
- document QA,
- repository QA,
- multi-hop reasoning,
- custom datasets.

The exact benchmark suite is unresolved.

---

## 10. Required research discipline

Need to define:
- fair baselines,
- datasets,
- ground truth,
- human evaluation,
- LLM-as-judge limitations,
- experiment count,
- statistical methodology,
- ablation studies,
- hardware reporting,
- reproducibility.

---

## 11. Ablation strategy

Potential ablations:
- baseline RAG,
- + requirement graph,
- + compiler,
- + Semantic IR,
- + progressive loading,
- + semantic cache,
- + Semantic Virtual Memory,
- + adaptive reasoning,
- + model routing.

This allows the project to show which components actually help.

---

## 12. Failure analysis

The project should preserve and analyze failures:
- missing required evidence,
- over-compression,
- lost dependency,
- stale cache,
- false sufficiency,
- unnecessary escalation,
- bad model routing,
- high page-fault overhead,
- latency regression.

A strong project should report limitations, not hide them.


---

# SOURCE FILE: 11_BUILD_ROADMAP_AND_VERSIONING.md

# PART 11 — BUILD ROADMAP AND VERSIONING

## 1. Build order agreed so far

### Stage 1 — Product and Research Foundation
Create:
- product thesis,
- research thesis,
- problem definition,
- novelty claims,
- system boundaries,
- non-goals,
- success metrics.

### Stage 2 — Architecture Specification
Define:
- service architecture,
- data architecture,
- runtime architecture,
- event architecture,
- Docker architecture,
- security boundaries,
- failure handling.

### Stage 3 — Frontend UX Architecture
Define:
- user journeys,
- information architecture,
- every major screen,
- interactions,
- visualization architecture,
- responsive behavior.

### Stage 4 — Visual Design System
Define:
- typography,
- spacing,
- layout,
- technical grid,
- surfaces,
- motion language,
- runtime-state colors,
- visualization rules,
- components.

### Stage 5 — Frontend With Simulated Executions
Build the major frontend using typed mock runtime events.

### Stage 6 — Baseline RAG
Build the conventional pipeline CortexOS must outperform.

### Stage 7 — Knowledge Ingestion
Build:
- parsing,
- structural segmentation,
- embeddings,
- metadata,
- relationships.

### Stage 8 — CortexOS Kernel V1
Implement:
- Task Profiler,
- Requirement Generator,
- Hybrid Retriever,
- Context Compiler,
- Sufficiency Evaluator.

### Stage 9 — Context Compiler
Build the complete compilation pipeline.

### Stage 10 — Benchmark Against Baseline
Prove whether token savings and quality retention exist.

### Stage 11 — Semantic Virtual Memory
Implement:
- semantic pages,
- memory states,
- page faults,
- eviction,
- pinning,
- invalidation,
- memory pressure.

### Stage 12 — Adaptive Inference
Implement:
- dynamic context budgets,
- reasoning depth,
- escalation,
- model routing.

### Stage 13 — Advanced Optimization
Potentially add:
- prefetching,
- counterfactual analysis,
- speculative context plans,
- context delta engine,
- utility prediction.

### Stage 14 — Learned Policy
Move from heuristics toward learned allocation.

### Stage 15 — Large-Scale Evaluation
Run:
- benchmark datasets,
- ablations,
- stress tests,
- failure analysis,
- quality evaluation.

### Stage 16 — Productionization
Complete:
- Docker hardening,
- security,
- observability,
- error recovery,
- documentation,
- CI/CD,
- public demo.

### Stage 17 — Recruitment Packaging
Produce:
- technical paper,
- architecture documentation,
- demo video,
- benchmark report,
- engineering case study,
- resume bullets,
- repository documentation.

---

## 2. Important sequencing rules

Do not:
- begin with RL,
- begin with multi-agent orchestration,
- begin with every advanced feature,
- build the full frontend only after the backend,
- claim performance before benchmarking.

Do:
- define the thesis,
- build a baseline,
- build a narrow vertical slice,
- measure it,
- add one optimization at a time,
- preserve traces and experiments.

---

## 3. Version buckets still need to be finalized

The feature set must be divided into:
- MVP,
- V1,
- V2,
- Research Track,
- Experimental Track.

A possible direction, not yet locked:

### MVP candidate
- baseline RAG,
- document/repository ingestion,
- Task Profiler,
- Requirement Generator,
- hybrid retrieval,
- Context Compiler,
- basic sufficiency loop,
- benchmark comparison,
- core Studio visualization,
- Docker Compose.

### V1 candidate
- Semantic IR,
- semantic cache,
- richer provenance,
- Semantic Virtual Memory basics,
- page faults,
- memory visualization.

### V2 candidate
- adaptive budgets,
- model routing,
- reasoning tiers,
- escalation.

### Research track
- context ablation,
- utility prediction,
- learned allocation.

### Experimental track
- speculative context execution,
- contextual bandits,
- offline policy learning,
- RL.

This division must be formally decided.


---

# SOURCE FILE: 12_OPEN_DECISIONS_AND_UNRESOLVED_PROBLEMS.md

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

## F. Zero-cost public deployment
Need:
- frontend hosting,
- public API strategy,
- replay architecture,
- trace hosting,
- live inference feasibility,
- sleep behavior,
- persistence,
- demo reliability,
- avoidance of unstable free-tier dependencies.

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


---

# SOURCE FILE: 13_CLAUDE_OPERATING_INSTRUCTIONS.md

# PART 13 — CLAUDE OPERATING INSTRUCTIONS

## 1. Role

Act as a principal AI systems architect, distributed systems engineer, research engineer, product architect, and technical specification author.

Your job is not to produce superficial ideas. Your job is to convert CortexOS into an implementation-ready, experimentally defensible, zero-cost, Docker-first system.

---

## 2. Non-negotiable behavior

### Do not silently change the project
Do not rename CortexOS or replace its core thesis.

### Do not simplify it into generic RAG
Every architecture decision must preserve the adaptive inference runtime vision.

### Do not over-engineer without proof
Advanced features must justify their existence through:
- measurable benefit,
- clear dependency,
- research value,
- or product necessity.

### Do not start coding prematurely
The project is currently specification-first.

### Do not invent benchmark results
All numerical performance results must come from real experiments.

### Do not introduce mandatory paid dependencies
The required implementation path must remain zero-cost.

### Do not introduce cloud-only architecture
The full runtime must be runnable locally through Docker.

### Do not introduce a separate database or service casually
Prefer the smallest architecture that supports the research thesis.

### Do not begin with reinforcement learning
Start with heuristics and measurable baselines.

---

## 3. Required specification quality

Every future implementation-ready specification should define, where applicable:

- purpose,
- scope,
- non-goals,
- inputs,
- outputs,
- interfaces,
- schemas,
- algorithms,
- state transitions,
- invariants,
- failure modes,
- security concerns,
- observability,
- metrics,
- tests,
- acceptance criteria,
- dependencies,
- unresolved decisions.

A file should not be labeled implementation-ready unless an engineer can implement it without inventing major behavior.

---

## 4. Required architecture reasoning

For every major component, answer:

1. Why does it exist?
2. What exact problem does it solve?
3. Why is a simpler design insufficient?
4. What data enters it?
5. What data leaves it?
6. What state does it own?
7. What are its failure modes?
8. How is it measured?
9. How is it tested?
10. How does it support the core research thesis?

---

## 5. Required zero-cost discipline

For every dependency or hosted component:
- identify whether it is open source,
- identify whether it can run locally,
- identify hardware expectations,
- avoid mandatory commercial APIs,
- avoid architecture that only works with paid managed services.

If public hosting depends on a free tier, separate it from the full local runtime so the project remains reproducible if the free tier disappears.

---

## 6. Required Docker discipline

The final project must support a reproducible local workflow.

Design for:
- Docker Compose,
- service health checks,
- persistent data,
- deterministic startup,
- migrations,
- seed/demo data,
- resource limits,
- CPU-only fallback,
- dev and production modes.

---

## 7. Frontend discipline

CortexOS Studio must visualize real system semantics.

Do not add animation merely for decoration.

Every major visualization should map to:
- runtime state,
- execution event,
- benchmark result,
- memory state,
- context decision,
- or system metric.

---

## 8. Research discipline

Separate:
- hypothesis,
- architecture,
- experiment,
- result,
- conclusion.

Design fair baselines.

Use ablations.

Report limitations.

Preserve experiment configuration and hardware details.

---

## 9. Immediate requested next work

The next major deliverable should be:

# CORTEXOS MASTER SPEC 000
## Product Thesis, Research Claims, System Boundaries, Constraints, and Success Metrics

It should settle:
- why CortexOS exists,
- exact problem statement,
- primary user,
- first use case,
- product form,
- genuine novelty,
- primary hypothesis,
- secondary hypotheses,
- MVP,
- non-goals,
- system boundaries,
- zero-cost constraints,
- Docker constraints,
- measurable success criteria,
- path from MVP to final system.

Before writing SPEC 000, identify any decision that genuinely cannot be made from the current context and present the smallest necessary decision set. Do not reopen already locked decisions.
