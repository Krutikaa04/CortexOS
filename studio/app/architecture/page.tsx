"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRepo } from "@/lib/repo-context";
import type {
  Architecture,
  CycleItem,
  DeadCodeItem,
  InsightsOverview,
} from "@/lib/types";
import { ForceGraph, type FGNode } from "@/components/ForceGraph";
import { IconSpinner } from "@/components/icons";

const EDGE_KIND_COLOR: Record<string, string> = {
  imports: "#5aa7ff",
  calls: "#4dd0e1",
  inherits: "#a78bfa",
  references_doc: "#ffc75f",
  documents: "#ffc75f",
};

export default function ArchitecturePage() {
  const { versionId, selected, loading } = useRepo();
  const [arch, setArch] = useState<Architecture | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [selectedFile, setSelectedFile] = useState<FGNode | null>(null);

  useEffect(() => {
    if (!versionId) return;
    let active = true;
    setBusy(true);
    setError(null);
    api
      .architecture(versionId)
      .then((a) => active && setArch(a))
      .catch((e) => active && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => active && setBusy(false));
    return () => {
      active = false;
    };
  }, [versionId]);

  const { nodes, edges, edgeKinds } = useMemo(() => {
    if (!arch) return { nodes: [] as FGNode[], edges: [], edgeKinds: [] as string[] };
    const connected = new Set<string>();
    arch.edges.forEach((e) => {
      connected.add(e.from);
      connected.add(e.to);
    });
    const degree: Record<string, number> = {};
    arch.edges.forEach((e) => {
      degree[e.from] = (degree[e.from] ?? 0) + e.weight;
      degree[e.to] = (degree[e.to] ?? 0) + e.weight;
    });
    const files = arch.files.filter((f) => showAll || connected.has(f.id));
    const ids = new Set(files.map((f) => f.id));
    const kinds = [...new Set(arch.edges.map((e) => e.kind))];
    return {
      nodes: files.map((f) => ({
        id: f.id,
        label: f.path.split("/").pop() ?? f.path,
        sub: f.path,
        kind: f.language ?? "file",
        degree: degree[f.id] ?? 1,
      })),
      edges: arch.edges.filter((e) => ids.has(e.from) && ids.has(e.to)),
      edgeKinds: kinds,
    };
  }, [arch, showAll]);

  const fileById = useMemo(() => {
    const m = new Map(arch?.files.map((f) => [f.id, f]) ?? []);
    return m;
  }, [arch]);

  if (!loading && !versionId)
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-400">
        Select a ready repository to see its architecture.
      </div>
    );

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-8 py-8">
        <header className="mb-4 flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink-100">Architecture</h1>
            <p className="mt-1 text-sm text-ink-400">
              File-level dependency map for {selected?.display_name}, generated
              from the ingested graph — each edge is a real relationship between
              artifacts in two files.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-ink-400">
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => setShowAll(e.target.checked)}
              className="accent-signal-blue"
            />
            show unconnected files
          </label>
        </header>

        {/* edge-kind legend */}
        <div className="mb-3 flex flex-wrap gap-2">
          {edgeKinds.map((k) => (
            <span key={k} className="chip">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: EDGE_KIND_COLOR[k] ?? "#8593ab" }}
              />
              {k}
            </span>
          ))}
        </div>

        {error && (
          <div className="panel border-signal-red/30 p-4 text-sm text-signal-red">{error}</div>
        )}

        {busy && !arch ? (
          <div className="panel flex h-[560px] items-center justify-center text-sm text-ink-500">
            <IconSpinner /> <span className="ml-2">Generating architecture…</span>
          </div>
        ) : (
          arch && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_260px]">
              <div>
                <ForceGraph nodes={nodes} edges={edges} onSelect={setSelectedFile} />
                <div className="mt-2 text-[11px] text-ink-500">
                  {nodes.length} files · {edges.length} dependencies
                </div>
              </div>

              <aside className="space-y-3">
                <div className="panel p-4">
                  <div className="stat-label">Overview</div>
                  <div className="mt-2 space-y-1.5 text-sm">
                    <Line label="Files" value={arch.files.length} />
                    <Line label="Dependencies" value={arch.edges.length} />
                    <Line
                      label="Artifacts"
                      value={arch.files.reduce((s, f) => s + f.artifacts, 0)}
                    />
                  </div>
                </div>

                {selectedFile && (
                  <div className="panel animate-fade-up p-4">
                    <div className="stat-label">Selected file</div>
                    <div className="mt-2 break-all font-mono text-[12px] text-ink-100">
                      {fileById.get(selectedFile.id)?.path}
                    </div>
                    <div className="mt-2 space-y-1.5 text-sm">
                      <Line
                        label="Artifacts"
                        value={fileById.get(selectedFile.id)?.artifacts ?? 0}
                      />
                      <Line
                        label="Tokens"
                        value={(fileById.get(selectedFile.id)?.tokens ?? 0).toLocaleString()}
                      />
                      <Line label="Language" value={selectedFile.kind} />
                    </div>
                  </div>
                )}
              </aside>
            </div>
          )
        )}

        {versionId && <EngineeringIntelligence versionId={versionId} />}
      </div>
    </div>
  );
}

function EngineeringIntelligence({ versionId }: { versionId: string }) {
  const [overview, setOverview] = useState<InsightsOverview | null>(null);
  const [dead, setDead] = useState<DeadCodeItem[] | null>(null);
  const [cycles, setCycles] = useState<CycleItem[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    setBusy(true);
    Promise.allSettled([
      api.insightsOverview(versionId),
      api.deadCode(versionId),
      api.cycles(versionId),
    ]).then(([o, d, c]) => {
      if (!active) return;
      if (o.status === "fulfilled") setOverview(o.value);
      if (d.status === "fulfilled") setDead(d.value.items);
      if (c.status === "fulfilled") setCycles(c.value.cycles);
      setBusy(false);
    });
    return () => {
      active = false;
    };
  }, [versionId]);

  return (
    <section className="mt-8">
      <h2 className="text-lg font-semibold text-ink-100">Engineering intelligence</h2>
      <p className="mt-1 text-sm text-ink-400">
        Deterministic analyses over the repository graph — every finding carries its evidence.
      </p>
      {busy && !overview ? (
        <div className="panel mt-3 flex h-32 items-center justify-center text-sm text-ink-500">
          <IconSpinner /> <span className="ml-2">Analyzing graph…</span>
        </div>
      ) : (
        <div className="mt-3 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {overview && (
            <div className="panel p-4">
              <div className="stat-label">Architecture layers</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {overview.layers.map((l) => (
                  <span key={l.layer} className="chip">
                    {l.layer.replace(/_/g, " ")} · {l.files}
                  </span>
                ))}
              </div>
              <div className="mt-4 stat-label">Hotspots (most referenced)</div>
              <ul className="mt-2 space-y-1">
                {overview.hotspots.slice(0, 6).map((h) => (
                  <li key={h.qualified_name} className="flex justify-between gap-2 text-[13px]">
                    <span className="truncate font-mono text-ink-200">{h.symbol}</span>
                    <span className="shrink-0 text-ink-500">{h.references} refs</span>
                  </li>
                ))}
                {overview.hotspots.length === 0 && (
                  <li className="text-[13px] text-ink-500">No references recorded.</li>
                )}
              </ul>
              <div className="mt-4 stat-label">High coupling</div>
              <ul className="mt-2 space-y-1">
                {overview.high_coupling.slice(0, 5).map((f) => (
                  <li key={f.path} className="flex justify-between gap-2 text-[12.5px]">
                    <span className="truncate font-mono text-ink-300">{f.path}</span>
                    <span className="shrink-0 text-ink-500" title={f.evidence}>
                      {f.coupling}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="space-y-4">
            <div className="panel p-4">
              <div className="flex items-center justify-between">
                <div className="stat-label">Circular dependencies</div>
                <span className="badge bg-ink-800 text-ink-300">{cycles?.length ?? 0}</span>
              </div>
              {cycles && cycles.length > 0 ? (
                <ul className="mt-2 space-y-2">
                  {cycles.slice(0, 5).map((c, i) => (
                    <li key={i} className="rounded-lg border border-signal-red/20 bg-signal-red/5 p-2">
                      <div className="font-mono text-[11.5px] text-ink-200">
                        {c.files.map((f) => f.split("/").pop()).join(" → ")} → …
                      </div>
                      <div className="mt-1 text-[11px] text-ink-500">{c.resolution}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="mt-2 text-[13px] text-signal-green">No dependency cycles found.</div>
              )}
            </div>

            <div className="panel p-4">
              <div className="flex items-center justify-between">
                <div className="stat-label">Potential dead code</div>
                <span className="badge bg-ink-800 text-ink-300">{dead?.length ?? 0}</span>
              </div>
              {dead && dead.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {dead.slice(0, 8).map((d) => (
                    <li key={d.qualified_name} className="flex justify-between gap-2 text-[12.5px]">
                      <span className="truncate font-mono text-ink-200" title={d.evidence}>
                        {d.symbol}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-ink-600">{d.path}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="mt-2 text-[13px] text-ink-400">
                  No unreferenced functions/classes detected.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Line({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-ink-400">{label}</span>
      <span className="font-mono text-ink-100">{value}</span>
    </div>
  );
}
