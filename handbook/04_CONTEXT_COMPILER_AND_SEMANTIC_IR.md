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
