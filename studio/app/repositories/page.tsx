"use client";

import { useRepo } from "@/lib/repo-context";
import { AddSourceForm } from "@/components/AddSourceForm";
import { IconCheck } from "@/components/icons";

export default function RepositoriesPage() {
  const { sources, selected, select, refresh, offline } = useRepo();

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-4xl px-8 py-8">
        <header className="mb-6">
          <h1 className="text-xl font-semibold text-ink-100">Repositories</h1>
          <p className="mt-1 text-sm text-ink-400">
            Ingested repositories CortexOS can reason over. Select one to make it
            active across Chat, Architecture and the Knowledge Graph.
          </p>
        </header>

        <div className="panel mb-6 overflow-hidden">
          <AddSourceForm onQueued={refresh} />
        </div>

        {offline && (
          <div className="panel border-signal-amber/30 p-4 text-sm text-signal-amber">
            Runtime not reachable — start it with{" "}
            <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-xs">
              docker compose up
            </code>
            .
          </div>
        )}

        <div className="space-y-2">
          {sources === null && !offline && (
            <div className="p-4 text-sm text-ink-500">Loading…</div>
          )}
          {sources?.length === 0 && (
            <div className="panel p-8 text-center text-sm text-ink-500">
              No repositories yet. Add one above to get started.
            </div>
          )}
          {sources?.map((s) => {
            const v = s.latest_version;
            const ready = v?.status === "ready";
            const activeSel = s.id === selected?.id;
            return (
              <button
                key={s.id}
                onClick={() => ready && select(s.id)}
                disabled={!ready}
                className={`panel flex w-full items-center justify-between p-4 text-left transition-colors ${
                  ready ? "hover:border-ink-600" : "opacity-70"
                } ${activeSel ? "border-signal-blue/50 ring-1 ring-signal-blue/20" : ""}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-medium text-ink-100">
                      {s.display_name}
                    </span>
                    {activeSel && (
                      <span className="badge bg-signal-blue/10 text-signal-blue">
                        <IconCheck className="h-3 w-3" /> active
                      </span>
                    )}
                  </div>
                  <div className="mt-1 truncate font-mono text-[11px] text-ink-500">
                    {s.uri}
                  </div>
                  {v && (
                    <div className="mt-1 font-mono text-[11px] text-ink-500">
                      {v.commit_sha.slice(0, 10)} · {v.stats?.artifacts ?? "?"} artifacts ·{" "}
                      {v.stats?.edges ?? "?"} edges · {v.stats?.files ?? "?"} files
                    </div>
                  )}
                </div>
                <span
                  className={`badge shrink-0 ${
                    ready
                      ? "bg-signal-green/10 text-signal-green"
                      : v?.status === "failed"
                        ? "bg-signal-red/10 text-signal-red"
                        : "bg-signal-amber/10 text-signal-amber"
                  }`}
                >
                  {v?.status ?? "empty"}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
