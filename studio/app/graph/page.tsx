"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRepo } from "@/lib/repo-context";
import type { RepoGraph } from "@/lib/types";
import {
  ForceGraph,
  KIND_COLORS,
  type FGNode,
} from "@/components/ForceGraph";
import { ArtifactDrawer, type ArtifactTarget } from "@/components/ArtifactDrawer";
import { IconSpinner } from "@/components/icons";

export default function GraphPage() {
  const { versionId, selected, loading } = useRepo();
  const [graph, setGraph] = useState<RepoGraph | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [limit, setLimit] = useState(140);
  const [drawer, setDrawer] = useState<ArtifactTarget | null>(null);

  useEffect(() => {
    if (!versionId) return;
    let active = true;
    setBusy(true);
    setError(null);
    api
      .graph(versionId, limit)
      .then((g) => active && setGraph(g))
      .catch((e) => active && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => active && setBusy(false));
    return () => {
      active = false;
    };
  }, [versionId, limit]);

  const kinds = useMemo(() => {
    const s = new Map<string, number>();
    graph?.nodes.forEach((n) => s.set(n.kind, (s.get(n.kind) ?? 0) + 1));
    return [...s.entries()].sort((a, b) => b[1] - a[1]);
  }, [graph]);

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as FGNode[], edges: [] };
    const visible = graph.nodes.filter((n) => !hidden.has(n.kind));
    const ids = new Set(visible.map((n) => n.id));
    return {
      nodes: visible.map((n) => ({
        id: n.id,
        label: n.label,
        kind: n.kind,
        degree: n.degree,
      })),
      edges: graph.edges.filter((e) => ids.has(e.from) && ids.has(e.to)),
    };
  }, [graph, hidden]);

  if (!loading && !versionId)
    return <NeedRepo name={selected?.display_name} />;

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-8 py-8">
        <header className="mb-4 flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink-100">Knowledge Graph</h1>
            <p className="mt-1 text-sm text-ink-400">
              The real semantic graph of {selected?.display_name} — artifacts and
              their typed relationships. Drag to explore, click a node to read
              its source.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-ink-400">
            nodes
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-ink-200 outline-none"
            >
              {[80, 140, 220, 400].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </header>

        {/* kind legend / filter */}
        <div className="mb-3 flex flex-wrap gap-2">
          {kinds.map(([kind, count]) => {
            const off = hidden.has(kind);
            return (
              <button
                key={kind}
                onClick={() =>
                  setHidden((prev) => {
                    const next = new Set(prev);
                    next.has(kind) ? next.delete(kind) : next.add(kind);
                    return next;
                  })
                }
                className={`chip ${off ? "opacity-40" : ""}`}
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: KIND_COLORS[kind] ?? "#8593ab" }}
                />
                {kind} <span className="text-ink-500">{count}</span>
              </button>
            );
          })}
        </div>

        {error && (
          <div className="panel border-signal-red/30 p-4 text-sm text-signal-red">{error}</div>
        )}

        {busy && !graph ? (
          <div className="panel flex h-[560px] items-center justify-center text-sm text-ink-500">
            <IconSpinner /> <span className="ml-2">Loading graph…</span>
          </div>
        ) : (
          graph && (
            <>
              <ForceGraph
                nodes={nodes}
                edges={edges}
                onSelect={(n) =>
                  versionId && setDrawer({ versionId, artifactId: n.id })
                }
              />
              <div className="mt-2 text-[11px] text-ink-500">
                {nodes.length} nodes · {edges.length} edges
                {graph.truncated && " · showing the most connected artifacts"}
              </div>
            </>
          )
        )}
      </div>
      <ArtifactDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}

function NeedRepo({ name }: { name?: string }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-400">
      {name ? `${name} is not ready yet.` : "Select a ready repository to view its graph."}
    </div>
  );
}
