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
