"""Semantic Virtual Memory — session-scoped page residency.

The context window is treated as managed working memory:

  semantic page   one artifact at a chosen representation level
  ACTIVE          resident in the session's stable prompt prefix
  page fault      a requirement is not covered by resident pages
  page-in         artifact enters the prefix (append-only, stable seq)
  eviction        memory pressure removes lowest-value unpinned pages
  invalidation    re-ingestion marks pages of changed artifacts INVALID

Why append-only order matters: the model runtime (Ollama) reuses its KV
cache when a request shares a prefix with the previous request. Keeping
resident pages at stable positions means later turns in a session only
pay prompt-processing for NEW pages and the question — an honest,
runtime-measured saving (visible in prompt_eval_count), not bookkeeping.

Eviction deliberately breaks the prefix (pages disappear from it); the
next turn pays a one-time cache rebuild. That is real memory-pressure
behavior and is reported, not hidden.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text

from cortex.db import get_session_factory

log = logging.getLogger("cortex.svm")

# Maximum tokens of ACTIVE pages per session. Exceeding triggers eviction.
SESSION_BUDGET_TOKENS = 6000


@dataclass
class Page:
    artifact_id: uuid.UUID
    qualified_name: str
    path: str
    representation: str
    text: str
    tokens: int
    seq: int
    pinned: bool


async def get_active_pages(session_id: uuid.UUID) -> list[Page]:
    """Resident pages in stable prefix order."""
    async with get_session_factory()() as s:
        rows = (
            await s.execute(
                text(
                    "SELECT p.artifact_id, p.representation, p.tokens, p.seq, p.pinned, "
                    "       a.qualified_name, a.raw_text, a.facts, sf.path "
                    "FROM svm_page p "
                    "JOIN semantic_artifact a ON a.id = p.artifact_id "
                    "JOIN source_file sf ON sf.id = a.source_file_id "
                    "WHERE p.session_id = :sid AND p.state = 'active' "
                    "ORDER BY p.seq"
                ),
                {"sid": session_id},
            )
        ).all()
    return [
        Page(
            artifact_id=r.artifact_id,
            qualified_name=r.qualified_name,
            path=r.path,
            representation=r.representation,
            text=_render(r.raw_text, r.facts, r.representation),
            tokens=r.tokens,
            seq=r.seq,
            pinned=r.pinned,
        )
        for r in rows
    ]


async def page_in(
    session_id: uuid.UUID,
    artifact_id: uuid.UUID,
    representation: str,
    tokens: int,
) -> int:
    """Make a page resident; returns its seq. Idempotent per (session, artifact)."""
    async with get_session_factory()() as s:
        seq = (
            await s.execute(
                text("SELECT coalesce(max(seq), 0) + 1 FROM svm_page WHERE session_id = :sid"),
                {"sid": session_id},
            )
        ).scalar_one()
        await s.execute(
            text(
                "INSERT INTO svm_page "
                "(id, session_id, artifact_id, state, seq, tokens, representation, use_count) "
                "VALUES (:id, :sid, :aid, 'active', :seq, :tokens, :repr, 1) "
                "ON CONFLICT (session_id, artifact_id) DO UPDATE SET "
                "  state = 'active', use_count = svm_page.use_count + 1, last_used_at = now()"
            ),
            {"id": uuid.uuid4(), "sid": session_id, "aid": artifact_id,
             "seq": seq, "tokens": tokens, "repr": representation},
        )
        await s.commit()
    return seq


async def touch_pages(session_id: uuid.UUID, artifact_ids: list[uuid.UUID]) -> None:
    """Record reuse of resident pages (drives eviction value)."""
    if not artifact_ids:
        return
    async with get_session_factory()() as s:
        await s.execute(
            text(
                "UPDATE svm_page SET use_count = use_count + 1, last_used_at = now() "
                "WHERE session_id = :sid AND artifact_id = ANY(:aids)"
            ),
            {"sid": session_id, "aids": artifact_ids},
        )
        await s.commit()


async def evict_if_needed(
    session_id: uuid.UUID, incoming_tokens: int
) -> list[dict]:
    """Evict lowest-value unpinned pages until incoming fits the budget.

    Value = use_count recency-weighted; MVP heuristic: oldest last_used_at,
    lowest use_count first. Returns descriptions of evicted pages.
    """
    evicted: list[dict] = []
    async with get_session_factory()() as s:
        active_tokens = (
            await s.execute(
                text("SELECT coalesce(sum(tokens), 0) FROM svm_page "
                     "WHERE session_id = :sid AND state = 'active'"),
                {"sid": session_id},
            )
        ).scalar_one()

        overflow = active_tokens + incoming_tokens - SESSION_BUDGET_TOKENS
        if overflow <= 0:
            return []

        victims = (
            await s.execute(
                text(
                    "SELECT p.id, p.artifact_id, p.tokens, a.qualified_name "
                    "FROM svm_page p JOIN semantic_artifact a ON a.id = p.artifact_id "
                    "WHERE p.session_id = :sid AND p.state = 'active' AND NOT p.pinned "
                    "ORDER BY p.use_count ASC, p.last_used_at ASC"
                ),
                {"sid": session_id},
            )
        ).all()
        freed = 0
        for v in victims:
            if freed >= overflow:
                break
            await s.execute(
                text("UPDATE svm_page SET state = 'evicted' WHERE id = :id"), {"id": v.id}
            )
            freed += v.tokens
            evicted.append(
                {"artifact_id": str(v.artifact_id), "qualified_name": v.qualified_name,
                 "tokens": v.tokens}
            )
        await s.commit()
    if evicted:
        log.info("session %s: evicted %d pages (%d tokens)", session_id, len(evicted), freed)
    return evicted


async def invalidate_artifacts(artifact_ids: list[uuid.UUID]) -> int:
    """Mark pages of changed/superseded artifacts INVALID across all sessions."""
    if not artifact_ids:
        return 0
    async with get_session_factory()() as s:
        result = await s.execute(
            text(
                "UPDATE svm_page SET state = 'invalid' "
                "WHERE artifact_id = ANY(:aids) AND state = 'active'"
            ),
            {"aids": artifact_ids},
        )
        await s.commit()
    return result.rowcount or 0


async def invalidate_superseded_version(old_version_id: uuid.UUID) -> int:
    """Invalidate all resident pages belonging to a superseded source version."""
    async with get_session_factory()() as s:
        result = await s.execute(
            text(
                "UPDATE svm_page SET state = 'invalid' "
                "WHERE state = 'active' AND artifact_id IN ("
                "  SELECT id FROM semantic_artifact WHERE source_version_id = :vid)"
            ),
            {"vid": old_version_id},
        )
        await s.commit()
    return result.rowcount or 0


def _render(raw_text: str, facts: list | None, representation: str) -> str:
    """Deterministic page rendering — MUST be stable across turns, or the
    prompt prefix changes and the runtime's KV cache misses."""
    if representation == "facts" and facts:
        lines = []
        for fact in facts:
            if fact.get("type") == "signature":
                lines.append(fact["value"])
            elif fact.get("type") == "constant":
                lines.append(f"{fact['name']} = {fact['value']}")
            elif fact.get("type") == "fact":
                lines.append(f"{fact['subject']} {fact['predicate']} {fact['object']}")
        if lines:
            return "\n".join(lines)
    return raw_text
