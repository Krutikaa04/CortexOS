"""Engineering-intelligence analyses over the existing Knowledge Graph.

Every function here is *deterministic graph reasoning* — no inference is spent
(the Inference Budget Controller philosophy), so these analyses are fast,
evidence-backed and reproducible. They power Dead Code, Circular Dependencies,
Repository Insights, Architecture Layers and Request-Flow tracing by reusing
the same `semantic_artifact` / `artifact_edge` rows the rest of the Kernel
uses. The pure functions take plain structures so they are unit-testable
without a database.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.kernel.impact import classify_dimension

# Edges that mean "A depends on B" (A --kind--> B). Mirrors the impact guard.
DEPENDENCY_EDGE_KINDS = ("calls", "imports", "inherits", "references_doc", "documents")

# Symbols the framework/runtime invokes even with no inbound graph edge, so
# they must never be reported as dead. Kept as data for one source of truth.
_ENTRYPOINT_RE = (
    "main", "__main__", "handler", "handle", "route", "router", "view",
    "endpoint", "app", "setup", "index", "default",
)


# ------------------------------------------------------------- pure analyses


def detect_cycles(edges: list[tuple[str, str]], max_cycles: int = 50) -> list[list[str]]:
    """Directed-cycle detection (DFS). `edges` are (from, to) = 'from depends on
    to'. Returns distinct cycles as node-id lists (dependency order)."""
    adj: dict[str, list[str]] = {}
    for a, b in edges:
        if a != b:
            adj.setdefault(a, []).append(b)

    cycles: list[list[str]] = []
    seen: set[frozenset] = set()
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(u: str) -> None:
        if len(cycles) >= max_cycles:
            return
        color[u] = GREY
        stack.append(u)
        for v in adj.get(u, ()):
            if color.get(v, WHITE) == GREY:  # back-edge → cycle
                cyc = stack[stack.index(v):]
                key = frozenset(cyc)
                if len(cyc) > 1 and key not in seen:
                    seen.add(key)
                    cycles.append(list(cyc))
            elif color.get(v, WHITE) == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for node in list(adj):
        if color.get(node, WHITE) == WHITE:
            dfs(node)
    return cycles


def _is_entrypoint(node: dict) -> bool:
    name = node["qualified_name"].split("::")[-1].split(".")[-1].lower()
    if name.startswith("__") and name.endswith("__"):
        return True  # dunder — invoked by the runtime
    if any(k in name for k in _ENTRYPOINT_RE):
        return True
    # test functions/files are invoked by the test runner, not the graph
    path = node["path"].lower()
    return "test" in path or name.startswith("test")


def detect_dead_code(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Functions/classes/methods with no inbound dependency edge and not a
    framework entrypoint — reported only with the evidence that justifies it.

    Modules and doc sections are excluded (they are addressed by imports at a
    different granularity and are frequently package entrypoints)."""
    referenced: set[str] = {e["to_id"] for e in edges if e["kind"] in DEPENDENCY_EDGE_KINDS}
    dead: list[dict] = []
    for n in nodes:
        if n["kind"] not in ("function", "method", "class"):
            continue
        if n["id"] in referenced or _is_entrypoint(n):
            continue
        dead.append({
            "qualified_name": n["qualified_name"],
            "symbol": n["qualified_name"].split("::")[-1],
            "path": n["path"],
            "kind": n["kind"],
            "evidence": "no inbound calls, imports, or inheritance in the graph",
        })
    return dead


def repository_insights(nodes: list[dict], edges: list[dict]) -> dict:
    """Repository-level signals with evidence: large modules, high coupling,
    hotspots (most-referenced), and architecture-layer distribution."""
    inbound: dict[str, int] = {}
    outbound: dict[str, int] = {}
    for e in edges:
        if e["kind"] not in DEPENDENCY_EDGE_KINDS:
            continue
        inbound[e["to_id"]] = inbound.get(e["to_id"], 0) + 1
        outbound[e["from_id"]] = outbound.get(e["from_id"], 0) + 1

    by_file: dict[str, dict] = {}
    for n in nodes:
        f = by_file.setdefault(n["path"], {"path": n["path"], "artifacts": 0, "tokens": 0,
                                           "in": 0, "out": 0})
        f["artifacts"] += 1
        f["tokens"] += n.get("tokens", 0) or 0
        f["in"] += inbound.get(n["id"], 0)
        f["out"] += outbound.get(n["id"], 0)
    files = list(by_file.values())

    def top(items, key, n=8):
        return sorted(items, key=key, reverse=True)[:n]

    large_modules = [
        {"path": f["path"], "tokens": f["tokens"], "artifacts": f["artifacts"],
         "evidence": f"{f['artifacts']} artifacts, {f['tokens']} tokens"}
        for f in top(files, lambda f: f["tokens"]) if f["tokens"] > 0
    ]
    high_coupling = [
        {"path": f["path"], "coupling": f["in"] + f["out"], "fan_in": f["in"], "fan_out": f["out"],
         "evidence": f"{f['in']} inbound + {f['out']} outbound dependencies"}
        for f in top(files, lambda f: f["in"] + f["out"]) if f["in"] + f["out"] > 0
    ]
    hotspots = [
        {"qualified_name": n["qualified_name"], "symbol": n["qualified_name"].split("::")[-1],
         "path": n["path"], "references": inbound.get(n["id"], 0),
         "evidence": f"referenced by {inbound.get(n['id'], 0)} other artifact(s)"}
        for n in top(nodes, lambda n: inbound.get(n["id"], 0)) if inbound.get(n["id"], 0) > 0
    ]

    layers: dict[str, int] = {}
    for f in files:
        dim = classify_dimension(f["path"], f["path"])
        layers[dim] = layers.get(dim, 0) + 1

    return {
        "large_modules": large_modules,
        "high_coupling": high_coupling,
        "hotspots": hotspots,
        "layers": [{"layer": k, "files": v} for k, v in
                   sorted(layers.items(), key=lambda kv: kv[1], reverse=True)],
        "totals": {"files": len(files), "artifacts": len(nodes),
                   "dependencies": sum(1 for e in edges if e["kind"] in DEPENDENCY_EDGE_KINDS)},
    }


def trace_flow(
    edges: list[dict], start_ids: list[str], max_depth: int = 6
) -> list[dict]:
    """Forward BFS over calls/imports from start artifacts: what the entrypoint
    reaches (service → repository → database), the downstream request flow."""
    adj: dict[str, list[tuple[str, str]]] = {}
    for e in edges:
        if e["kind"] in ("calls", "imports"):
            adj.setdefault(e["from_id"], []).append((e["to_id"], e["kind"]))
    levels: list[dict] = []
    seen = set(start_ids)
    frontier = list(start_ids)
    for depth in range(1, max_depth + 1):
        nxt: list[dict] = []
        next_ids: list[str] = []
        for u in frontier:
            for v, kind in adj.get(u, ()):
                if v in seen:
                    continue
                seen.add(v)
                next_ids.append(v)
                nxt.append({"id": v, "via": u, "edge_kind": kind})
        if not nxt:
            break
        levels.append({"depth": depth, "nodes": nxt})
        frontier = next_ids
    return levels


# ------------------------------------------------------------- DB layer


async def _load_graph(session: AsyncSession, version_id: uuid.UUID) -> tuple[list[dict], list[dict]]:
    node_rows = (
        await session.execute(
            text(
                "SELECT a.id, a.qualified_name, a.kind, a.raw_token_count AS tokens, sf.path "
                "FROM semantic_artifact a JOIN source_file sf ON sf.id = a.source_file_id "
                "WHERE a.source_version_id = :vid"
            ),
            {"vid": version_id},
        )
    ).all()
    nodes = [
        {"id": str(r.id), "qualified_name": r.qualified_name, "kind": r.kind,
         "tokens": r.tokens, "path": r.path}
        for r in node_rows
    ]
    edge_rows = (
        await session.execute(
            text(
                "SELECT from_artifact_id, to_artifact_id, kind FROM artifact_edge "
                "WHERE source_version_id = :vid"
            ),
            {"vid": version_id},
        )
    ).all()
    edges = [
        {"from_id": str(r.from_artifact_id), "to_id": str(r.to_artifact_id), "kind": r.kind}
        for r in edge_rows
    ]
    return nodes, edges


def _file_dependency_edges(nodes: list[dict], edges: list[dict]) -> list[tuple[str, str]]:
    """Collapse artifact edges to file→file dependency edges (for cycles)."""
    path_of = {n["id"]: n["path"] for n in nodes}
    out: set[tuple[str, str]] = set()
    for e in edges:
        if e["kind"] not in DEPENDENCY_EDGE_KINDS:
            continue
        a, b = path_of.get(e["from_id"]), path_of.get(e["to_id"])
        if a and b and a != b:
            out.add((a, b))
    return list(out)


async def analyze_dead_code(session: AsyncSession, version_id: uuid.UUID) -> dict:
    nodes, edges = await _load_graph(session, version_id)
    dead = detect_dead_code(nodes, edges)
    return {"count": len(dead), "items": dead}


async def analyze_cycles(session: AsyncSession, version_id: uuid.UUID) -> dict:
    nodes, edges = await _load_graph(session, version_id)
    file_edges = _file_dependency_edges(nodes, edges)
    cycles = detect_cycles(file_edges)
    return {
        "count": len(cycles),
        "cycles": [
            {"files": c, "length": len(c),
             "risk": "HIGH" if len(c) <= 2 else "MEDIUM",
             "impact": "tight coupling; changes ripple across the cycle",
             "resolution": "invert one dependency (extract an interface/shared module) to break the loop"}
            for c in cycles
        ],
    }


async def analyze_insights(session: AsyncSession, version_id: uuid.UUID) -> dict:
    nodes, edges = await _load_graph(session, version_id)
    return repository_insights(nodes, edges)


async def analyze_flow(
    session: AsyncSession, version_id: uuid.UUID, qualified_name: str
) -> dict:
    nodes, edges = await _load_graph(session, version_id)
    by_id = {n["id"]: n for n in nodes}
    starts = [n["id"] for n in nodes if n["qualified_name"] == qualified_name
              or n["qualified_name"].split("::")[-1] == qualified_name]
    if not starts:
        return {"start": qualified_name, "found": False, "levels": []}
    levels = trace_flow(edges, starts[:1])
    rendered = [{
        "depth": lvl["depth"],
        "nodes": [{
            "qualified_name": by_id[x["id"]]["qualified_name"],
            "symbol": by_id[x["id"]]["qualified_name"].split("::")[-1],
            "path": by_id[x["id"]]["path"],
            "edge_kind": x["edge_kind"],
        } for x in lvl["nodes"] if x["id"] in by_id],
    } for lvl in levels]
    return {"start": qualified_name, "found": True,
            "start_symbol": by_id[starts[0]]["qualified_name"].split("::")[-1],
            "levels": rendered}
