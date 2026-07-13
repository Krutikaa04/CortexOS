"""Typed execution event stream.

Every important runtime decision is emitted as an append-only event row.
This single stream powers Studio's live view (SSE) and benchmark analysis.
Events are facts about what the runtime actually did on a real execution —
never fabricated, never retroactively edited.
"""

import uuid
from typing import Any

from sqlalchemy import text

from cortex.db import get_session_factory


class EventType:
    """Event vocabulary (handbook Part 03 §8). Extended as features land."""

    TASK_RECEIVED = "TASK_RECEIVED"
    TASK_PROFILED = "TASK_PROFILED"
    REQUIREMENTS_CREATED = "REQUIREMENTS_CREATED"
    RETRIEVAL_STARTED = "RETRIEVAL_STARTED"
    CANDIDATE_FOUND = "CANDIDATE_FOUND"
    CANDIDATE_REJECTED = "CANDIDATE_REJECTED"
    CONTEXT_DEDUPLICATED = "CONTEXT_DEDUPLICATED"
    CONTEXT_COMPRESSED = "CONTEXT_COMPRESSED"
    CONTEXT_COMPILED = "CONTEXT_COMPILED"
    MODEL_SELECTED = "MODEL_SELECTED"
    INFERENCE_STARTED = "INFERENCE_STARTED"
    INFERENCE_COMPLETED = "INFERENCE_COMPLETED"
    PAGE_FAULT = "PAGE_FAULT"
    PAGE_IN = "PAGE_IN"
    PAGE_OUT = "PAGE_OUT"
    EVICT = "EVICT"
    PIN = "PIN"
    INVALIDATE = "INVALIDATE"
    SUFFICIENCY_CHECKED = "SUFFICIENCY_CHECKED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    EXECUTION_FAILED = "EXECUTION_FAILED"

    # Change Impact Guard phases (streamed to Studio's Impact Guard view)
    IMPACT_STARTED = "IMPACT_STARTED"
    IMPACT_DIFF_PARSED = "IMPACT_DIFF_PARSED"
    IMPACT_ARTIFACTS_RESOLVED = "IMPACT_ARTIFACTS_RESOLVED"
    IMPACT_BLAST_RADIUS = "IMPACT_BLAST_RADIUS"
    IMPACT_RISK_SCORED = "IMPACT_RISK_SCORED"
    IMPACT_EVIDENCE_COMPILED = "IMPACT_EVIDENCE_COMPILED"
    IMPACT_NARRATIVE = "IMPACT_NARRATIVE"
    IMPACT_COMPLETED = "IMPACT_COMPLETED"


class EventEmitter:
    """Per-execution emitter maintaining the sequence counter."""

    def __init__(self, execution_id: uuid.UUID) -> None:
        self.execution_id = execution_id
        self._seq = 0

    async def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self._seq += 1
        async with get_session_factory()() as session:
            await session.execute(
                text(
                    "INSERT INTO execution_event (execution_id, seq, event_type, payload) "
                    "VALUES (:eid, :seq, :type, cast(:payload as jsonb))"
                ),
                {
                    "eid": self.execution_id,
                    "seq": self._seq,
                    "type": event_type,
                    "payload": _json(payload or {}),
                },
            )
            await session.commit()


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
