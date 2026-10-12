"""Neo4j Knowledge Graph store (Graph-RAG backbone).

The graph is a *projection* of the semantic artifacts and typed edges that
ingestion already writes to Postgres — Neo4j holds structure and pointers
(artifact id, path, name, span), never source text. Source content stays in
``semantic_artifact.raw_text`` and is resolved by artifact id after traversal.

Isolation: every node carries ``vid`` (the source_version id) and every query
below filters on it server-side. Nodes are keyed ``"<vid>:<id>"`` so two
repositories can never share or link a node.

Optional by configuration: with ``NEO4J_URI`` empty the graph is disabled and
callers fall back to the Postgres retriever (and report that honestly).
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy import text

from cortex.config import get_settings

log = logging.getLogger("cortex.graphstore")

# artifact kind -> Neo4j label (whitelist: labels/rel types cannot be parameters)
KIND_LABEL = {
    "module": "Module", "class": "Class", "function": "Function", "method": "Method",
    "doc_section": "Doc", "config_entry": "Config",
}
# artifact_edge.kind -> relationship type
REL_TYPE = {
    "imports": "IMPORTS", "calls": "CALLS", "inherits": "EXTENDS", "contains": "CONTAINS",
    "references_doc": "REFERENCES", "documents": "DOCUMENTS", "supersedes": "SUPERSEDES",
}
# Relationship types followed during question-time traversal. CONTAINS and
# DEFINES are structural scaffolding, excluded to avoid hub fan-out.
TRAVERSE_RELS = "CALLS|IMPORTS|EXTENDS|REFERENCES|DOCUMENTS"
MAX_HOPS = 3
BATCH = 1000
_CODE_LANGS = ("python", "javascript")

_driver = None


class GraphUnavailable(RuntimeError):
    """Neo4j is configured but cannot be reached / queried."""


def enabled() -> bool:
    return get_settings().graph_enabled


def _get_driver():
    global _driver
    if _driver is None:
        from neo4j import AsyncGraphDatabase

        s = get_settings()
        _driver = AsyncGraphDatabase.driver(
            s.neo4j_uri, auth=(s.neo4j_username, s.neo4j_password),
            connection_timeout=5, max_connection_lifetime=1800,
        )
    return _driver


async def close() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def _run(query: str, **params: Any) -> list[dict]:
    from neo4j import Query

    try:
        async with _get_driver().session(database=get_settings().neo4j_database) as s:
            result = await s.run(Query(query, timeout=20), params)
            return [r.data() async for r in result]
    except Exception as exc:  # noqa: BLE001 — surface one typed error to callers
        raise GraphUnavailable(f"{type(exc).__name__}: {exc}") from exc


async def ping() -> bool:
    if not enabled():
        return False
    try:
        await _run("RETURN 1 AS ok")
        return True
    except GraphUnavailable:
        return False


async def _ensure_schema() -> None:
    await _run("CREATE CONSTRAINT cx_key IF NOT EXISTS FOR (n:CxNode) REQUIRE n.key IS UNIQUE")
    await _run("CREATE INDEX cx_vid IF NOT EXISTS FOR (n:CxNode) ON (n.vid)")


async def delete_graph(version_id: uuid.UUID | str) -> None:
    while True:
        rows = await _run(
            "MATCH (n:CxNode {vid: $vid}) WITH n LIMIT 5000 DETACH DELETE n RETURN count(*) AS c",
            vid=str(version_id),
        )
        if not rows or not rows[0]["c"]:
            return


def _symbol_name(qualified_name: str) -> str:
    if "::" in qualified_name:
        return qualified_name.split("::", 1)[1]
    return qualified_name.rsplit("/", 1)[-1]


async def build_graph(factory, source_id: uuid.UUID, version_id: uuid.UUID,
                      display_name: str, uri: str) -> dict:
    """Project one source version into Neo4j (idempotent: rebuilds the version).

    Returns measured stats for ``source_version.stats['graph']``.
    """
    vid = str(version_id)
    await _ensure_schema()
    await delete_graph(version_id)

    async with factory() as session:
        files = (await session.execute(
            text("SELECT id, path, language FROM source_file WHERE source_version_id = :v"),
            {"v": version_id})).all()
        arts = (await session.execute(
            text("SELECT id, source_file_id, kind, qualified_name, span_start_line, "
                 "span_end_line FROM semantic_artifact WHERE source_version_id = :v"),
            {"v": version_id})).all()
        edges = (await session.execute(
            text("SELECT from_artifact_id, to_artifact_id, kind, confidence "
                 "FROM artifact_edge WHERE source_version_id = :v"),
            {"v": version_id})).all()

    file_by_id = {f.id: f for f in files}
    await _run(
        "MERGE (r:CxNode {key: $key}) SET r:Repository, r.vid = $vid, r.sid = $sid, "
        "r.name = $name, r.lname = toLower($name), r.uri = $uri",
        key=f"{vid}:repo", vid=vid, sid=str(source_id), name=display_name, uri=uri,
    )

    # File nodes + Repository CONTAINS File
    file_rows = [{"key": f"{vid}:f:{f.id}", "path": f.path, "lang": f.language or "text",
                  "name": f.path.rsplit("/", 1)[-1]} for f in files]
    for i in range(0, len(file_rows), BATCH):
        await _run(
            "UNWIND $rows AS r MERGE (n:CxNode {key: r.key}) "
            "SET n:File, n.vid = $vid, n.path = r.path, n.lpath = toLower(r.path), "
            "n.lang = r.lang, n.name = r.name, n.lname = toLower(r.name) "
            "WITH n MATCH (repo:CxNode {key: $rk}) MERGE (repo)-[:CONTAINS]->(n)",
            rows=file_rows[i:i + BATCH], vid=vid, rk=f"{vid}:repo",
        )

    # Symbol nodes grouped by label, each File DEFINES its symbols
    by_label: dict[str, list[dict]] = {}
    for a in arts:
        f = file_by_id.get(a.source_file_id)
        if f is None:
            continue
        name = _symbol_name(a.qualified_name)
        by_label.setdefault(KIND_LABEL.get(a.kind, "Symbol"), []).append({
            "key": f"{vid}:{a.id}", "aid": str(a.id), "fkey": f"{vid}:f:{f.id}",
            "qn": a.qualified_name, "name": name, "kind": a.kind, "path": f.path,
            "lang": f.language or "text", "start": a.span_start_line, "end": a.span_end_line,
        })
    for label, rows in by_label.items():
        for i in range(0, len(rows), BATCH):
            await _run(
                f"UNWIND $rows AS r MERGE (n:CxNode {{key: r.key}}) SET n:{label}, "
                "n.vid = $vid, n.aid = r.aid, n.qn = r.qn, n.name = r.name, "
                "n.lname = toLower(r.name), n.kind = r.kind, n.path = r.path, "
                "n.lang = r.lang, n.start = r.start, n.end = r.end "
                "WITH n, r MATCH (f:CxNode {key: r.fkey}) MERGE (f)-[:DEFINES]->(n)",
                rows=rows[i:i + BATCH], vid=vid,
            )

    # Typed relationships between symbols, grouped by relationship type
    by_rel: dict[str, list[dict]] = {}
    for e in edges:
        rel = REL_TYPE.get(e.kind)
        if rel:
            by_rel.setdefault(rel, []).append(
                {"a": f"{vid}:{e.from_artifact_id}", "b": f"{vid}:{e.to_artifact_id}",
                 "conf": float(e.confidence)})
    for rel, rows in by_rel.items():
        for i in range(0, len(rows), BATCH):
            await _run(
                "UNWIND $rows AS r MATCH (a:CxNode {key: r.a}), (b:CxNode {key: r.b}) "
                f"MERGE (a)-[x:{rel}]->(b) SET x.conf = r.conf",
                rows=rows[i:i + BATCH],
            )

    code_files = {f.id for f in files if f.language in _CODE_LANGS}
    parsed = {a.source_file_id for a in arts
              if a.kind != "module" and a.source_file_id in code_files}
    live = await graph_stats(version_id)
    languages: dict[str, int] = {}
    for f in files:
        languages[f.language or "text"] = languages.get(f.language or "text", 0) + 1
    return {
        "status": "ready", "nodes": live["nodes"], "edges": live["edges"],
        "files": len(files), "languages": languages,
        # measured: share of code files parsed into symbols (rest are file-level)
        "coverage": round(len(parsed) / len(code_files), 3) if code_files else None,
    }


async def graph_stats(version_id: uuid.UUID | str) -> dict:
    vid = str(version_id)
    n = await _run("MATCH (n:CxNode {vid: $vid}) RETURN count(n) AS c", vid=vid)
    e = await _run("MATCH (:CxNode {vid: $vid})-[r]->(:CxNode {vid: $vid}) RETURN count(r) AS c",
                   vid=vid)
    return {"nodes": n[0]["c"], "edges": e[0]["c"]}


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_STOP = frozenset(
    "the and for with what when how why does did are was were this that from into "
    "which where who would should could about happens happen code file files "
    "function functions class classes method methods".split()
)


def query_tokens(query: str) -> list[str]:
    """Lower-cased lookup tokens: words, CamelCase/snake_case parts, 4-char
    stems of long words ('authentication' -> 'auth')."""
    out: list[str] = []
    for w in _TOKEN.findall(query):
        parts = [w] + re.findall(r"[A-Z][a-z0-9]+|[a-z0-9]+", w) if (
            "_" in w or any(c.isupper() for c in w[1:])) else [w]
        for p in parts:
            p = p.lower()
            if len(p) >= 3 and p not in _STOP and p not in out:
                out.append(p)
            if len(p) >= 8 and p[:4] not in out:
                out.append(p[:4])
    return out[:16]


async def name_anchors(version_id: uuid.UUID, tokens: list[str], limit: int = 8) -> list[dict]:
    """Symbols whose name matches the query — structural anchors, scoped by vid."""
    if not tokens:
        return []
    return await _run(
        "MATCH (n:CxNode {vid: $vid}) WHERE n.aid IS NOT NULL AND n.kind <> 'doc_section' "
        "AND any(t IN $tokens WHERE n.lname CONTAINS t) "
        "WITH n, size([t IN $tokens WHERE n.lname CONTAINS t]) AS hits "
        "RETURN n.aid AS aid, hits ORDER BY hits DESC, size(n.name) ASC LIMIT $lim",
        vid=str(version_id), tokens=tokens, lim=limit,
    )


async def expand(version_id: uuid.UUID, anchors: list[str], hops: int, direction: str = "both",
                 per_hop_limit: int | None = None) -> dict:
    """Bounded breadth-first traversal run server-side, one Cypher query per hop.

    ``direction``: 'both' follows edges either way; 'in' follows only
    dependents (nodes that point at the frontier) for blast-radius questions.
    Returns discovered nodes (with hop + the edge that reached them, so the
    reasoning path can be rebuilt) and measured examination counts.
    """
    vid = str(version_id)
    hops = max(1, min(hops, MAX_HOPS))
    lim = per_hop_limit or get_settings().graph_hop_limit
    arrow = "<-" if direction == "in" else "-"
    query = (
        f"MATCH (a:CxNode {{vid: $vid}}){arrow}[r:{TRAVERSE_RELS}]-(b:CxNode {{vid: $vid}}) "
        "WHERE a.key IN $keys AND b.aid IS NOT NULL AND NOT b.key IN $seen "
        "RETURN a.aid AS src, b.aid AS dst, b.name AS name, b.kind AS kind, b.path AS path, "
        "type(r) AS rel, startNode(r) = a AS outgoing, coalesce(r.conf, 1.0) AS conf "
        "ORDER BY conf DESC LIMIT $lim"
    )
    nodes: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    seen = {f"{vid}:{a}" for a in anchors}
    frontier = list(anchors)
    edges_traversed = 0
    examined = len(anchors)
    # anchor display info
    if anchors:
        for r in await _run(
            "MATCH (n:CxNode {vid: $vid}) WHERE n.key IN $keys "
            "RETURN n.aid AS aid, n.name AS name, n.kind AS kind, n.path AS path",
            vid=vid, keys=[f"{vid}:{a}" for a in anchors],
        ):
            meta[r["aid"]] = {"name": r["name"], "kind": r["kind"], "path": r["path"]}
    for hop in range(1, hops + 1):
        if not frontier:
            break
        rows = await _run(query, vid=vid, keys=[f"{vid}:{a}" for a in frontier],
                          seen=list(seen), lim=lim)
        edges_traversed += len(rows)
        nxt: list[str] = []
        for r in rows:
            if r["dst"] in nodes:  # reached twice in one hop: keep the first (best-conf) edge
                continue
            nodes[r["dst"]] = {
                "hop": hop, "conf": r["conf"], "name": r["name"], "kind": r["kind"],
                "path": r["path"],
                "parent": {"aid": r["src"], "rel": r["rel"],
                           "from_parent": r["outgoing"]},
            }
            seen.add(f"{vid}:{r['dst']}")
            nxt.append(r["dst"])
        examined += len(nxt)
        frontier = nxt
    return {"nodes": nodes, "anchor_meta": meta, "edges_traversed": edges_traversed,
            "nodes_examined": examined, "hops": hops}


def reasoning_path(anchors: list[str], found: dict, selected: set[str]) -> dict:
    """Walk parent pointers from each selected node back to its anchor: the
    exact subgraph that justified the context CortexOS sent to the model."""
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple] = set()
    meta = found["anchor_meta"]
    for aid in anchors:
        if aid in meta:
            nodes[aid] = {"id": aid, **meta[aid], "anchor": True}
    for aid in selected:
        cur = aid
        guard = 0
        while cur in found["nodes"] and guard < MAX_HOPS + 1:
            n = found["nodes"][cur]
            nodes.setdefault(cur, {"id": cur, "name": n["name"], "kind": n["kind"],
                                   "path": n["path"]})
            p = n["parent"]
            a, b = (p["aid"], cur) if p["from_parent"] else (cur, p["aid"])
            if (a, b, p["rel"]) not in seen_edges:
                seen_edges.add((a, b, p["rel"]))
                edges.append({"from": a, "to": b, "type": p["rel"]})
            if p["aid"] not in nodes and p["aid"] in meta:
                nodes[p["aid"]] = {"id": p["aid"], **meta[p["aid"]], "anchor": True}
            cur = p["aid"]
            guard += 1
    return {"nodes": list(nodes.values()), "edges": edges}
