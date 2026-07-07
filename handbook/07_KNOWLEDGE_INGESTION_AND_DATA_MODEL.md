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
