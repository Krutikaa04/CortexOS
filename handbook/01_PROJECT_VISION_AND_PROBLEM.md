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
