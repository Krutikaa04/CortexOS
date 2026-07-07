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
