"""Trace export.

Exports real executions (with their full event streams) as self-contained
JSON bundles. These bundles power CortexOS Studio's public replay demo —
per the project's integrity rules, replay data must always originate from
real executions; this exporter is the only sanctioned way to produce it.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from cortex.db import get_session_factory

TRACE_FORMAT_VERSION = 1


async def export_execution_trace(execution_id: uuid.UUID) -> dict[str, Any]:
    """Build a replayable trace bundle for one execution."""
    async with get_session_factory()() as session:
        execution = (
            await session.execute(
                text(
                    "SELECT e.id, e.mode, e.query, e.answer, e.status, e.metrics, "
                    "       e.started_at, e.finished_at, e.session_id, "
                    "       v.commit_sha, s.display_name "
                    "FROM execution e "
                    "JOIN source_version v ON v.id = e.source_version_id "
                    "JOIN source s ON s.id = v.source_id "
                    "WHERE e.id = :id"
                ),
                {"id": execution_id},
            )
        ).first()
        if execution is None:
            raise ValueError(f"execution {execution_id} not found")

        events = (
            await session.execute(
                text(
                    "SELECT seq, event_type, payload, created_at FROM execution_event "
                    "WHERE execution_id = :id ORDER BY seq"
                ),
                {"id": execution_id},
            )
        ).all()

    return {
        "trace_format_version": TRACE_FORMAT_VERSION,
        "kind": "recorded_execution",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "execution": {
            "id": str(execution.id),
            "mode": execution.mode,
            "query": execution.query,
            "answer": execution.answer,
            "status": execution.status,
            "metrics": execution.metrics,
            "session_id": str(execution.session_id) if execution.session_id else None,
            "started_at": execution.started_at.isoformat(),
            "finished_at": execution.finished_at.isoformat()
            if execution.finished_at else None,
            "source": {
                "display_name": execution.display_name,
                "commit_sha": execution.commit_sha,
            },
        },
        "events": [
            {
                "seq": e.seq,
                "event_type": e.event_type,
                "payload": e.payload,
                "ts": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


async def export_trace_bundle(
    execution_ids: list[uuid.UUID], out_path: Path, title: str
) -> Path:
    """Export multiple executions into one demo bundle file."""
    traces = [await export_execution_trace(eid) for eid in execution_ids]
    bundle = {
        "trace_format_version": TRACE_FORMAT_VERSION,
        "kind": "trace_bundle",
        "title": title,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "traces": traces,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, indent=1, default=str), encoding="utf-8")
    return out_path
