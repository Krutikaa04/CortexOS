"use client";

// The repository Knowledge Graph as a working surface: stats, search, zoom/pan,
// node inspection (relationships + source), expand/collapse, and — when given a
// Graph-RAG reasoning path — the exact subgraph CortexOS used for an answer.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type {
  GraphPathEdge,
  GraphPathNode,
  GraphStats,
  Neighbors,
  RepoGraph,
} from "@/lib/types";
import { ForceGraph, type FGEdge, type FGNode } from "./ForceGraph";
import { IconSpinner } from "./icons";

export interface ReasoningPath {
  nodes: GraphPathNode[];
  edges: GraphPathEdge[];
}

export function KnowledgeGraphPanel({
  versionId,
  path,
  height = 460,
  limit = 160,
  onOpenSource,
}: {
  versionId: string;
  path?: ReasoningPath | null;
  height?: number;
  limit?: number;
  onOpenSource: (artifactId: string) => void;
}) {
  const [graph, setGraph] = useState<RepoGraph | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [extra, setExtra] = useState<{ nodes: Map<string, FGNode>; edges: FGEdge[] }>({
    nodes: new Map(),
    edges: [],
  });
  const [added, setAdded] = useState<Record<string, string[]>>({});
  const [selected, setSelected] = useState<FGNode | null>(null);
  const [neighbors, setNeighbors] = useState<Neighbors | null>(null);
  const [focusOnly, setFocusOnly] = useState(false);
  const [search, setSearch] = useState("");
  const [focusId, setFocusId] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    setGraph(null);
    setError(null);
    setExtra({ nodes: new Map(), edges: [] });
    setSelected(null);
    Promise.all([api.graph(versionId, limit), api.graphStats(versionId).catch(() => null)])
      .then(([g, s]) => {
        if (!active) return;
        setGraph(g);
        setStats(s);
      })
      .catch((e) => active && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      active = false;
    };
  }, [versionId, limit, reload]);

  // base graph + reasoning-path nodes (which may sit outside the top-N) + expansions
  const { nodes, edges } = useMemo(() => {
    const map = new Map<string, FGNode>();
    graph?.nodes.forEach((n) =>
      map.set(n.id, { id: n.id, label: n.label, kind: n.kind, degree: n.degree }),
    );
    path?.nodes.forEach((n) => {
      if (!map.has(n.id)) map.set(n.id, { id: n.id, label: n.name, kind: n.kind, degree: 3 });
    });
    extra.nodes.forEach((n, id) => !map.has(id) && map.set(id, n));
    const all: FGEdge[] = [...(graph?.edges ?? []), ...extra.edges];
    path?.edges.forEach((e) => all.push({ from: e.from, to: e.to, kind: e.type }));
    let ids = new Set(map.keys());
    if (focusOnly && selected) {
      const keep = new Set([selected.id]);
      all.forEach((e) => {
        if (e.from === selected.id) keep.add(e.to);
        if (e.to === selected.id) keep.add(e.from);
      });
      ids = keep;
    }
    const seen = new Set<string>();
    const outEdges = all.filter((e) => {
      const k = `${e.from}>${e.to}>${e.kind}`;
      if (seen.has(k) || !ids.has(e.from) || !ids.has(e.to)) return false;
      seen.add(k);
      return true;
    });
    return { nodes: [...map.values()].filter((n) => ids.has(n.id)), edges: outEdges };
  }, [graph, path, extra, focusOnly, selected]);

  const hlNodes = useMemo(() => new Set(path?.nodes.map((n) => n.id) ?? []), [path]);
  const hlEdges = useMemo(
    () => new Set(path?.edges.map((e) => `${e.from}>${e.to}`) ?? []),
    [path],
  );

  const select = useCallback(
    (n: FGNode) => {
      setSelected(n);
      setNeighbors(null);
      api.neighbors(versionId, n.id).then(setNeighbors).catch(() => setNeighbors(null));
    },
    [versionId],
  );

  const expand = () => {
    if (!selected || !neighbors) return;
    const ids: string[] = [];
    const nn = new Map(extra.nodes);
    const ee = [...extra.edges];
    const baseIds = new Set(graph?.nodes.map((n) => n.id));
    for (const d of neighbors.depends_on) {
      if (!baseIds.has(d.id) && !nn.has(d.id)) {
        nn.set(d.id, { id: d.id, label: d.symbol, kind: d.kind, degree: 2 });
        ids.push(d.id);
      }
      ee.push({ from: selected.id, to: d.id, kind: d.edge_kind });
    }
    for (const d of neighbors.dependents) {
      if (!baseIds.has(d.id) && !nn.has(d.id)) {
        nn.set(d.id, { id: d.id, label: d.symbol, kind: d.kind, degree: 2 });
        ids.push(d.id);
      }
      ee.push({ from: d.id, to: selected.id, kind: d.edge_kind });
    }
    setExtra({ nodes: nn, edges: ee });
    setAdded((a) => ({ ...a, [selected.id]: ids }));
  };

  const collapse = () => {
    if (!selected) return;
    const drop = new Set(added[selected.id] ?? []);
    const nn = new Map(extra.nodes);
    drop.forEach((id) => nn.delete(id));
    setExtra({
      nodes: nn,
      edges: extra.edges.filter(
        (e) =>
          !drop.has(e.from) &&
          !drop.has(e.to) &&
          !(e.from === selected.id || e.to === selected.id),
      ),
    });
    setAdded(({ [selected.id]: _, ...rest }) => rest);
  };

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [];
    return nodes.filter((n) => n.label.toLowerCase().includes(q)).slice(0, 6);
  }, [search, nodes]);

  const build = stats?.build;
  const building = build?.status === "building";
  const needsBuild = !!stats?.enabled && stats.available && build?.status !== "ready" && !building;

  // poll while a rebuild runs, then reload everything
  useEffect(() => {
    if (!building) return;
    const t = setInterval(async () => {
      const s = await api.graphStats(versionId).catch(() => null);
      if (s && s.build?.status !== "building") {
        setStats(s);
        setReload((n) => n + 1);
      }
    }, 3000);
    return () => clearInterval(t);
  }, [building, versionId]);

  const startBuild = async () => {
    try {
      await api.rebuildGraph(versionId);
      setStats((s) => (s ? { ...s, build: { status: "building" } } : s));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const coverage = build?.coverage;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-400">
        {needsBuild || building ? (
          <span className="flex items-center gap-2 text-signal-amber">
            {building
              ? "Building knowledge graph…"
              : build?.status === "failed"
                ? `Graph build failed${build.error ? `: ${build.error}` : ""}`
                : "This repository has no knowledge graph yet."}
            {!building && (
              <button className="chip" onClick={startBuild}>
                {build?.status === "failed" ? "Retry" : "Build knowledge graph"}
              </button>
            )}
          </span>
        ) : stats?.enabled && stats.available ? (
          <>
            <Stat n={stats.nodes} label="nodes" />
            <Stat n={stats.edges} label="edges" />
            <Stat n={build?.files} label="files" />
            {build?.languages && (
              <span>{Object.keys(build.languages).filter((l) => l !== "text").join(", ")}</span>
            )}
            {coverage != null && <span>{Math.round(coverage * 100)}% of code files parsed to symbols</span>}
          </>
        ) : stats && !stats.enabled ? (
          <span className="text-signal-amber">
            Neo4j not configured — Graph-RAG is off; showing the Postgres artifact graph.
          </span>
        ) : stats && !stats.available ? (
          <span className="text-signal-red">Neo4j unreachable{stats.error ? `: ${stats.error}` : ""}</span>
        ) : null}
        {path && path.nodes.length > 0 && (
          <span className="text-signal-amber">● reasoning path for this answer</span>
        )}
        <div className="relative ml-auto">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && matches[0]) {
                setFocusId(matches[0].id);
                select(matches[0]);
                setSearch("");
              }
            }}
            placeholder="Search nodes…"
            className="w-44 rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-xs text-ink-200 outline-none placeholder:text-ink-500 focus:border-signal-blue"
          />
          {matches.length > 0 && (
            <ul className="absolute right-0 z-10 mt-1 w-60 overflow-hidden rounded-md border border-ink-700 bg-ink-900 shadow-lg">
              {matches.map((m) => (
                <li key={m.id}>
                  <button
                    className="block w-full truncate px-2 py-1.5 text-left font-mono text-[11px] text-ink-200 hover:bg-ink-800"
                    onClick={() => {
                      setFocusId(m.id);
                      select(m);
                      setSearch("");
                    }}
                  >
                    {m.label} <span className="text-ink-500">{m.kind}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {error && <div className="panel border-signal-red/30 p-3 text-xs text-signal-red">{error}</div>}
      {!graph && !error && (
        <div
          className="panel flex items-center justify-center text-sm text-ink-500"
          style={{ height }}
        >
          <IconSpinner /> <span className="ml-2">Loading graph…</span>
        </div>
      )}
      {graph && (
        <div className="relative">
          <ForceGraph
            nodes={nodes}
            edges={edges}
            height={height}
            onSelect={select}
            highlightNodes={hlNodes}
            highlightEdges={hlEdges}
            focusId={focusId ?? selected?.id}
          />
          {selected && (
            <div className="absolute bottom-3 left-3 max-h-[70%] w-72 overflow-auto rounded-lg border border-ink-700 bg-ink-900/95 p-3 text-xs shadow-xl">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm text-ink-100">{selected.label}</div>
                  <div className="text-[10px] uppercase tracking-wider text-ink-500">
                    {selected.kind}
                  </div>
                </div>
                <button className="text-ink-500 hover:text-ink-200" onClick={() => setSelected(null)}>
                  ✕
                </button>
              </div>
              {neighbors ? (
                <>
                  <Rel title="Depends on" items={neighbors.depends_on} />
                  <Rel title="Used by" items={neighbors.dependents} />
                </>
              ) : (
                <div className="mt-2 text-ink-500">Loading relationships…</div>
              )}
              <div className="mt-3 flex flex-wrap gap-1.5">
                <button className="chip" onClick={() => onOpenSource(selected.id)}>
                  Open source
                </button>
                <button className="chip" disabled={!neighbors} onClick={expand}>
                  Expand
                </button>
                <button className="chip" onClick={collapse}>
                  Collapse
                </button>
                <button className="chip" onClick={() => setFocusOnly((f) => !f)}>
                  {focusOnly ? "Show all" : "Isolate"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      {graph && (
        <div className="text-[11px] text-ink-500">
          showing {nodes.length} nodes · {edges.length} edges
          {graph.truncated && " · most-connected subset (search to find others)"}
        </div>
      )}
    </div>
  );
}

function Stat({ n, label }: { n: number | null | undefined; label: string }) {
  return n == null ? null : (
    <span>
      <span className="font-mono text-ink-200">{n.toLocaleString()}</span> {label}
    </span>
  );
}

function Rel({ title, items }: { title: string; items: Neighbors["depends_on"] }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2">
      <div className="text-[10px] uppercase tracking-wider text-ink-500">{title}</div>
      <ul className="mt-1 space-y-0.5">
        {items.slice(0, 8).map((d) => (
          <li key={d.id + d.edge_kind} className="truncate font-mono text-[11px] text-ink-300">
            <span className="text-ink-500">{d.edge_kind.toUpperCase()}</span> {d.symbol}
          </li>
        ))}
        {items.length > 8 && <li className="text-ink-500">+{items.length - 8} more</li>}
      </ul>
      <div className="mt-0.5 truncate text-[10px] text-ink-600">{items[0]?.path}</div>
    </div>
  );
}
