"""Read endpoints over the ingested knowledge graph.

The runtime already stores the full semantic graph (artifacts + typed edges)
and the source files behind it. These endpoints expose that real, ingested
data so Studio can render the Knowledge Graph, derive an Architecture view,
and show the exact code an answer used — with links back to the file and to
GitHub. Nothing here is synthesized: every node, edge, and snippet is a row.
"""

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.db import get_session

router = APIRouter(prefix="/v1/sources", tags=["graph"])


def _github_blob_url(uri: str, commit_sha: str, path: str,
                     start: int | None = None, end: int | None = None) -> str | None:
    """Build a GitHub blob URL when the source is a GitHub repo, else None.

    Handles both https and scp-style git remotes; returns None for local
    paths so the frontend can fall back to an in-app file view.
    """
    if not uri:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", uri.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    ref = commit_sha or "HEAD"
    url = f"https://github.com/{owner}/{repo}/blob/{ref}/{path.lstrip('/')}"
    if start:
        url += f"#L{start}" + (f"-L{end}" if end and end != start else "")
    return url


async def _resolve_version(session: AsyncSession, version_id: uuid.UUID) -> tuple[str, str]:
    """Return (source_uri, commit_sha) for a ready version, or 404."""
    row = (
        await session.execute(
            text(
                "SELECT s.uri, v.commit_sha FROM source_version v "
                "JOIN source s ON s.id = v.source_id WHERE v.id = :id"
            ),
            {"id": version_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="source version not found")
    return row.uri, row.commit_sha


@router.get("/{version_id}/graph")
async def get_graph(
    version_id: uuid.UUID,
    limit: int = Query(400, ge=1, le=2000),
    kinds: str | None = Query(None, description="comma-separated artifact kinds to include"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Nodes (semantic artifacts) and typed edges for one ingested version.

    Nodes are ranked by connectivity so a bounded ``limit`` returns the most
    structurally important artifacts first; edges are restricted to the
    returned node set so the graph is always internally consistent.
    """
    await _resolve_version(session, version_id)

    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    params: dict = {"vid": version_id, "limit": limit}
    kind_filter = ""
    if kind_list:
        kind_filter = "AND a.kind = ANY(:kinds)"
        params["kinds"] = kind_list

    node_rows = (
        await session.execute(
            text(
                "SELECT a.id, a.qualified_name, a.kind, a.raw_token_count, "
                "       f.path, f.language, "
                "       (SELECT count(*) FROM artifact_edge e "
                "        WHERE e.from_artifact_id = a.id OR e.to_artifact_id = a.id) AS degree "
                "FROM semantic_artifact a "
                "JOIN source_file f ON f.id = a.source_file_id "
                f"WHERE a.source_version_id = :vid {kind_filter} "
                "ORDER BY degree DESC, a.raw_token_count DESC "
                "LIMIT :limit"
            ),
            params,
        )
    ).all()

    node_ids = [r.id for r in node_rows]
    nodes = [
        {
            "id": str(r.id),
            "qualified_name": r.qualified_name,
            "label": r.qualified_name.split("::")[-1] or r.qualified_name,
            "kind": r.kind,
            "path": r.path,
            "language": r.language,
            "tokens": r.raw_token_count,
            "degree": int(r.degree),
        }
        for r in node_rows
    ]

    edges: list[dict] = []
    if node_ids:
        edge_rows = (
            await session.execute(
                text(
                    "SELECT from_artifact_id, to_artifact_id, kind FROM artifact_edge "
                    "WHERE source_version_id = :vid "
                    "AND from_artifact_id = ANY(:ids) AND to_artifact_id = ANY(:ids)"
                ),
                {"vid": version_id, "ids": node_ids},
            )
        ).all()
        edges = [
            {"from": str(r.from_artifact_id), "to": str(r.to_artifact_id), "kind": r.kind}
            for r in edge_rows
        ]

    return {"version_id": str(version_id), "nodes": nodes, "edges": edges,
            "truncated": len(nodes) >= limit}


@router.get("/{version_id}/architecture")
async def get_architecture(
    version_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict:
    """File/module-level architecture, aggregated from the artifact graph.

    Each node is a source file; each edge is the count of artifact-level
    relationships crossing between two files (imports/calls/inherits). This
    is a real projection of the ingested graph, not a hand-drawn diagram.
    """
    await _resolve_version(session, version_id)

    file_rows = (
        await session.execute(
            text(
                "SELECT f.id, f.path, f.language, count(a.id) AS artifacts, "
                "       coalesce(sum(a.raw_token_count), 0) AS tokens "
                "FROM source_file f "
                "LEFT JOIN semantic_artifact a ON a.source_file_id = f.id "
                "WHERE f.source_version_id = :vid "
                "GROUP BY f.id, f.path, f.language ORDER BY f.path"
            ),
            {"vid": version_id},
        )
    ).all()
    files = {
        str(r.id): {
            "id": str(r.id),
            "path": r.path,
            "language": r.language,
            "artifacts": int(r.artifacts),
            "tokens": int(r.tokens),
        }
        for r in file_rows
    }

    edge_rows = (
        await session.execute(
            text(
                "SELECT af.source_file_id AS from_file, at.source_file_id AS to_file, "
                "       e.kind, count(*) AS weight "
                "FROM artifact_edge e "
                "JOIN semantic_artifact af ON af.id = e.from_artifact_id "
                "JOIN semantic_artifact at ON at.id = e.to_artifact_id "
                "WHERE e.source_version_id = :vid "
                "AND af.source_file_id <> at.source_file_id "
                "GROUP BY af.source_file_id, at.source_file_id, e.kind"
            ),
            {"vid": version_id},
        )
    ).all()
    edges = [
        {"from": str(r.from_file), "to": str(r.to_file), "kind": r.kind, "weight": int(r.weight)}
        for r in edge_rows
    ]

    return {"version_id": str(version_id), "files": list(files.values()), "edges": edges}


@router.get("/{version_id}/artifacts/{artifact_id}")
async def get_artifact(
    version_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Full detail for one artifact: source code, span, and outbound links."""
    uri, commit_sha = await _resolve_version(session, version_id)
    row = (
        await session.execute(
            text(
                "SELECT a.id, a.qualified_name, a.kind, a.raw_text, a.summary_text, "
                "       a.facts, a.span_start_line, a.span_end_line, a.raw_token_count, "
                "       f.path, f.language "
                "FROM semantic_artifact a JOIN source_file f ON f.id = a.source_file_id "
                "WHERE a.id = :id AND a.source_version_id = :vid"
            ),
            {"id": artifact_id, "vid": version_id},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {
        "id": str(row.id),
        "qualified_name": row.qualified_name,
        "kind": row.kind,
        "path": row.path,
        "language": row.language,
        "span_start_line": row.span_start_line,
        "span_end_line": row.span_end_line,
        "tokens": row.raw_token_count,
        "raw_text": row.raw_text,
        "summary_text": row.summary_text,
        "facts": row.facts,
        "github_url": _github_blob_url(
            uri, commit_sha, row.path, row.span_start_line, row.span_end_line
        ),
    }


@router.get("/{version_id}/artifacts/{artifact_id}/neighbors")
async def get_neighbors(
    version_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Direct graph neighbours of one artifact, split into what it depends on
    (outbound edges) and what depends on it (inbound edges). Powers the
    Dependency Explorer's 'what depends on this / what will break' view."""
    await _resolve_version(session, version_id)

    async def _side(where: str, join_on: str) -> list[dict]:
        rows = (
            await session.execute(
                text(
                    "SELECT a.id, a.qualified_name, a.kind, sf.path, e.kind AS edge_kind "
                    "FROM artifact_edge e "
                    f"JOIN semantic_artifact a ON a.id = {join_on} "
                    "JOIN source_file sf ON sf.id = a.source_file_id "
                    f"WHERE e.source_version_id = :vid AND {where} = :aid "
                    "AND e.kind <> 'contains'"
                ),
                {"vid": version_id, "aid": artifact_id},
            )
        ).all()
        return [
            {
                "id": str(r.id),
                "qualified_name": r.qualified_name,
                "symbol": r.qualified_name.split("::")[-1],
                "kind": r.kind,
                "path": r.path,
                "edge_kind": r.edge_kind,
            }
            for r in rows
        ]

    # outbound: this --edge--> X  => depends_on X
    depends_on = await _side("e.from_artifact_id", "e.to_artifact_id")
    # inbound: X --edge--> this   => X depends on / could break if this changes
    dependents = await _side("e.to_artifact_id", "e.from_artifact_id")
    return {"depends_on": depends_on, "dependents": dependents}


@router.get("/{version_id}/lookup")
async def lookup_artifact(
    version_id: uuid.UUID,
    qualified_name: str = Query(..., description="exact qualified_name to resolve"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Resolve a qualified_name (as it appears in execution events) to its id.

    Lets Studio turn the ``path::symbol`` strings in a compiled-context event
    into a clickable artifact without embedding ids in the event stream.
    """
    uri, commit_sha = await _resolve_version(session, version_id)
    row = (
        await session.execute(
            text(
                "SELECT a.id, a.qualified_name, a.kind, a.span_start_line, "
                "       a.span_end_line, f.path, f.language "
                "FROM semantic_artifact a JOIN source_file f ON f.id = a.source_file_id "
                "WHERE a.source_version_id = :vid AND a.qualified_name = :qn LIMIT 1"
            ),
            {"vid": version_id, "qn": qualified_name},
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {
        "id": str(row.id),
        "qualified_name": row.qualified_name,
        "kind": row.kind,
        "path": row.path,
        "language": row.language,
        "span_start_line": row.span_start_line,
        "span_end_line": row.span_end_line,
        "github_url": _github_blob_url(
            uri, commit_sha, row.path, row.span_start_line, row.span_end_line
        ),
    }
