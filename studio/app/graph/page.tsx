"use client";

import { useState } from "react";
import { useRepo } from "@/lib/repo-context";
import { KnowledgeGraphPanel } from "@/components/KnowledgeGraphPanel";
import { ArtifactDrawer, type ArtifactTarget } from "@/components/ArtifactDrawer";

export default function GraphPage() {
  const { versionId, selected, loading } = useRepo();
  const [limit, setLimit] = useState(160);
  const [drawer, setDrawer] = useState<ArtifactTarget | null>(null);

  if (!loading && !versionId)
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-400">
        {selected?.display_name
          ? `${selected.display_name} is not ready yet.`
          : "Select a ready repository to view its graph."}
      </div>
    );

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-8 py-8">
        <header className="mb-4 flex items-end justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink-100">Knowledge Graph</h1>
            <p className="mt-1 text-sm text-ink-400">
              How {selected?.display_name} is connected. CortexOS traverses this graph to find
              the code relevant to each question. Click a node to inspect, expand or open its
              source.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs text-ink-400">
            nodes
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="rounded-md border border-ink-700 bg-ink-850 px-2 py-1 text-ink-200 outline-none"
            >
              {[80, 160, 260, 400].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </header>
        {versionId && (
          <KnowledgeGraphPanel
            versionId={versionId}
            limit={limit}
            height={600}
            onOpenSource={(artifactId) => setDrawer({ versionId, artifactId })}
          />
        )}
      </div>
      <ArtifactDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
