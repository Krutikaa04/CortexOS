"""Answer cache for repeated questions (Postgres-backed; no extra service).

Key = hash of (repository version, normalized question, graph version,
retrieval/model configuration, pipeline revision). Versions are immutable
snapshots, so a hit is by construction an answer to the same question over
the same code, graph and settings - anything that could change the answer
changes the key, and nothing is ever "invalidated", only no longer reachable.

A hit re-serves the stored answer, metrics and event trail. The metrics are
the *original run's* measurements; ``metrics.cache`` says it was served from
cache so the UI never presents them as spent now.

Not cached: baseline-mode runs (benchmarks need real runs), executions that
failed, and answers produced while the graph was degraded (Neo4j error).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid

from sqlalchemy import text

from cortex.config import get_settings

# Bump when retrieval / prompting logic changes in a way that alters answers.
PIPELINE_REV = "graph-rag-2"
TTL_DAYS = 30


# An answer saying the context lacked the information is a retrieval miss, not a
# result worth re-serving for 30 days.
_ADMITS_GAP = re.compile(
    r"(does not|doesn't|do not|cannot|can't|could not|unable to)\b[^.]{0,40}"
    r"\b(contain|find|provide|include|determine|answer)|no information|not enough information",
    re.I,
)


def normalize(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower()).rstrip("?.! ")


def graph_version(graph_stats: dict | None) -> str:
    """Identity of the graph the answer was retrieved from."""
    g = graph_stats or {}
    return f"{g.get('status', 'none')}:{g.get('nodes', 0)}:{g.get('edges', 0)}"


def make_key(version_id: uuid.UUID, query: str, graph_stats: dict | None) -> str:
    s = get_settings()
    material = json.dumps(
        {
            "v": str(version_id), "q": normalize(query), "g": graph_version(graph_stats),
            "rev": PIPELINE_REV, "task": s.task_model, "internal": s.internal_model,
            "embed": s.embed_model, "hops": s.graph_max_hops,
            "hop_limit": s.graph_hop_limit, "min_conf": s.graph_min_confidence,
            "graph_on": s.graph_enabled,
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode()).hexdigest()


async def lookup(session, key: str) -> dict | None:
    row = (await session.execute(
        text("SELECT execution_id, answer, metrics FROM answer_cache "
             "WHERE key = :k AND created_at > now() - make_interval(days => :d)"),
        {"k": key, "d": TTL_DAYS},
    )).first()
    if row is None:
        return None
    await session.execute(text("UPDATE answer_cache SET hits = hits + 1 WHERE key = :k"),
                          {"k": key})
    return {"execution_id": row.execution_id, "answer": row.answer, "metrics": row.metrics}


async def store(session, key: str, version_id: uuid.UUID, query: str,
                execution_id: uuid.UUID, answer: str, metrics: dict) -> None:
    gr = metrics.get("graph_rag") or {}
    if not answer or gr.get("graph_error") or _ADMITS_GAP.search(answer[:200]):
        return  # never cache empty, degraded-retrieval or "context was insufficient" answers
    await session.execute(
        text("INSERT INTO answer_cache (key, source_version_id, query, execution_id, "
             "answer, metrics) VALUES (:k, :v, :q, :e, :a, cast(:m as jsonb)) "
             "ON CONFLICT (key) DO UPDATE SET execution_id = EXCLUDED.execution_id, "
             "answer = EXCLUDED.answer, metrics = EXCLUDED.metrics, created_at = now(), hits = 0"),
        {"k": key, "v": version_id, "q": query[:2000], "e": execution_id,
         "a": answer, "m": json.dumps(metrics)},
    )
    await session.execute(
        text("DELETE FROM answer_cache WHERE created_at < now() - make_interval(days => :d)"),
        {"d": TTL_DAYS},
    )
