"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useRepo } from "@/lib/repo-context";
import type { Architecture } from "@/lib/types";
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
      </div>
    </div>
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
