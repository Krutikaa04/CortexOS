"""Hybrid Retriever.

Per requirement, combines:
- vector similarity over artifact embeddings (semantic recall),
- full-text search over raw artifact text (lexical precision),
- graph expansion along artifact edges (dependency context that similarity
  search systematically misses — the core bet of the project).

Returns candidates annotated with which requirements they serve and why
they were found, so the compiler and Context X-Ray can explain decisions.
"""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text

from cortex.db import get_session_factory
from cortex.kernel.profiler import TaskProfile
from cortex.kernel.requirements import Requirement
from cortex.models_client import get_model_client

log = logging.getLogger("cortex.kernel.retriever")

VECTOR_WEIGHT = 0.6
LEXICAL_WEIGHT = 0.4
GRAPH_DECAY = 0.6  # score multiplier per expansion hop


@dataclass
class Candidate:
    artifact_id: uuid.UUID
    qualified_name: str
    kind: str
    path: str
    raw_text: str
    facts: list | None
    summary_text: str | None
    raw_token_count: int
    score: float
    requirements: set[str] = field(default_factory=set)  # requirement ids served
    provenance: list[str] = field(default_factory=list)  # how it was found


async def retrieve(
    source_version_id: uuid.UUID,
    requirements: list[Requirement],
    profile: TaskProfile,
) -> list[Candidate]:
    client = get_model_client()
    candidates: dict[uuid.UUID, Candidate] = {}
    factory = get_session_factory()

    req_texts = [r.description for r in requirements]
    req_embeddings = await client.embed(req_texts)

    async with factory() as session:
        for req, embedding in zip(requirements, req_embeddings):
            # --- vector search ---
            rows = (
                await session.execute(
                    text(
                        "SELECT a.id, a.qualified_name, a.kind, a.raw_text, a.facts, "
                        "       a.summary_text, a.raw_token_count, sf.path, "
                        "       1 - (e.embedding <=> cast(:qe as vector)) AS similarity "
                        "FROM artifact_embedding e "
                        "JOIN semantic_artifact a ON a.id = e.artifact_id "
                        "JOIN source_file sf ON sf.id = a.source_file_id "
                        "WHERE a.source_version_id = :vid AND e.representation = 'raw' "
                        "ORDER BY e.embedding <=> cast(:qe as vector) "
                        "LIMIT :k"
                    ),
                    {"qe": str(embedding), "vid": source_version_id,
                     "k": profile.retrieval_top_k},
                )
            ).all()
            for r in rows:
                _merge(candidates, r, r.similarity * VECTOR_WEIGHT, req.id,
                       f"vector:{req.id}:{r.similarity:.3f}")

            # --- lexical search ---
            terms = " | ".join(k.replace("/", " ").replace(".", " ").strip()
                               for k in req.keywords if k.strip()) or req.description
            rows = (
                await session.execute(
                    text(
                        "SELECT a.id, a.qualified_name, a.kind, a.raw_text, a.facts, "
                        "       a.summary_text, a.raw_token_count, sf.path, "
                        "       ts_rank(to_tsvector('english', a.raw_text), query) AS rank "
                        "FROM semantic_artifact a "
                        "JOIN source_file sf ON sf.id = a.source_file_id, "
                        "     websearch_to_tsquery('english', :terms) query "
                        "WHERE a.source_version_id = :vid "
                        "  AND to_tsvector('english', a.raw_text) @@ query "
                        "ORDER BY rank DESC LIMIT :k"
                    ),
                    {"terms": terms.replace(" | ", " OR "), "vid": source_version_id,
                     "k": profile.retrieval_top_k // 2 + 1},
                )
            ).all()
            max_rank = max((r.rank for r in rows), default=1.0) or 1.0
            for r in rows:
                _merge(candidates, r, (r.rank / max_rank) * LEXICAL_WEIGHT, req.id,
                       f"lexical:{req.id}:{r.rank:.3f}")

        # --- graph expansion from the strongest hits ---
        if profile.dependency_depth > 0 and candidates:
            frontier = [c.artifact_id for c in
                        sorted(candidates.values(), key=lambda c: c.score, reverse=True)[:6]]
            seen = set(frontier)
            for hop in range(1, profile.dependency_depth + 1):
                if not frontier:
                    break
                rows = (
                    await session.execute(
                        text(
                            "SELECT a.id, a.qualified_name, a.kind, a.raw_text, a.facts, "
                            "       a.summary_text, a.raw_token_count, sf.path, "
                            "       ed.kind AS edge_kind, ed.confidence, "
                            "       ed.from_artifact_id, ed.to_artifact_id "
                            "FROM artifact_edge ed "
                            "JOIN semantic_artifact a "
                            "  ON a.id = CASE WHEN ed.from_artifact_id = ANY(:frontier) "
                            "            THEN ed.to_artifact_id ELSE ed.from_artifact_id END "
                            "JOIN source_file sf ON sf.id = a.source_file_id "
                            "WHERE (ed.from_artifact_id = ANY(:frontier) "
                            "       OR ed.to_artifact_id = ANY(:frontier)) "
                            "  AND ed.kind != 'contains'"
                        ),
                        {"frontier": frontier},
                    )
                ).all()
                next_frontier = []
                for r in rows:
                    if r.id in seen:
                        # still record that it's graph-connected
                        if r.id in candidates:
                            candidates[r.id].provenance.append(f"graph:hop{hop}:{r.edge_kind}")
                        continue
                    seen.add(r.id)
                    next_frontier.append(r.id)
                    base = max((candidates[f].score for f in frontier if f in candidates),
                               default=0.5)
                    _merge(candidates, r, base * (GRAPH_DECAY ** hop) * r.confidence,
                           "", f"graph:hop{hop}:{r.edge_kind}")
                frontier = next_frontier

    result = sorted(candidates.values(), key=lambda c: c.score, reverse=True)
    log.info("retrieved %d candidates across %d requirements", len(result), len(requirements))
    return result


def _merge(candidates: dict, row, score: float, req_id: str, provenance: str) -> None:
    existing = candidates.get(row.id)
    if existing is None:
        candidates[row.id] = Candidate(
            artifact_id=row.id,
            qualified_name=row.qualified_name,
            kind=row.kind,
            path=row.path,
            raw_text=row.raw_text,
            facts=row.facts,
            summary_text=row.summary_text,
            raw_token_count=row.raw_token_count,
            score=score,
            requirements={req_id} if req_id else set(),
            provenance=[provenance],
        )
    else:
        existing.score = max(existing.score, score) + 0.1 * min(existing.score, score)
        if req_id:
            existing.requirements.add(req_id)
        existing.provenance.append(provenance)
