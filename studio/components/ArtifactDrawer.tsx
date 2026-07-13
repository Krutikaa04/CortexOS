"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ArtifactDetail, DependencyNode, Neighbors } from "@/lib/types";
import { CopyButton } from "./CodeBlock";
import { IconClose, IconExternal, IconFile, IconGitHub, IconSpinner } from "./icons";

export interface ArtifactTarget {
  versionId: string;
  artifactId?: string;
  qualifiedName?: string;
}

type Tab = "source" | "dependencies";

export function ArtifactDrawer({
  target,
  onClose,
}: {
  target: ArtifactTarget | null;
  onClose: () => void;
}) {
  const [id, setId] = useState<string | null>(null);
  const [qn, setQn] = useState<string | undefined>(undefined);
  const [detail, setDetail] = useState<ArtifactDetail | null>(null);
  const [neighbors, setNeighbors] = useState<Neighbors | null>(null);
  const [tab, setTab] = useState<Tab>("source");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // (re)seed internal navigation whenever the drawer is opened on a new target
  useEffect(() => {
    if (!target) return;
    setId(target.artifactId ?? null);
    setQn(target.qualifiedName);
    setTab("source");
  }, [target]);

  const versionId = target?.versionId;

  // resolve id (from qualified_name if needed) + load detail & neighbors
  useEffect(() => {
    if (!versionId || (!id && !qn)) return;
    let active = true;
    setDetail(null);
    setNeighbors(null);
    setError(null);
    setLoading(true);
    (async () => {
      try {
        let artId = id;
        if (!artId && qn) {
          const ref = await api.lookup(versionId, qn);
          artId = ref.id;
          if (active) setId(ref.id);
        }
        if (!artId) throw new Error("artifact not found");
        const [d, n] = await Promise.all([
          api.artifact(versionId, artId),
          api.neighbors(versionId, artId).catch(() => null),
        ]);
        if (active) {
          setDetail(d);
          setNeighbors(n);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [versionId, id, qn]);

  const navigate = useCallback((nid: string) => {
    setId(nid);
    setQn(undefined);
    setTab("source");
  }, []);

  if (!target) return null;
  const depCount = (neighbors?.dependents.length ?? 0) + (neighbors?.depends_on.length ?? 0);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="animate-fade-up relative flex h-full w-full max-w-2xl flex-col border-l border-ink-800 bg-ink-950 shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-ink-800 px-5 py-3.5">
          <div className="min-w-0">
            <div className="truncate font-mono text-sm text-ink-100">
              {detail?.qualified_name.split("::").pop() ?? qn?.split("::").pop() ?? "Artifact"}
            </div>
            <div className="mt-0.5 truncate font-mono text-[11px] text-ink-500">
              {detail?.path ?? qn?.split("::")[0]}
              {detail && ` · L${detail.span_start_line}–${detail.span_end_line}`}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {detail && <CopyButton text={detail.raw_text} label="Copy source" />}
            {detail?.github_url && (
              <a href={detail.github_url} target="_blank" rel="noreferrer" className="btn-icon" title="Open on GitHub">
                <IconGitHub />
              </a>
            )}
            <button onClick={onClose} className="btn-icon" title="Close">
              <IconClose />
            </button>
          </div>
        </div>

        {/* tabs */}
        <div className="flex gap-1 border-b border-ink-800 px-3 pt-2">
          <TabBtn active={tab === "source"} onClick={() => setTab("source")}>
            Source
          </TabBtn>
          <TabBtn active={tab === "dependencies"} onClick={() => setTab("dependencies")}>
            Dependencies{depCount ? ` (${depCount})` : ""}
          </TabBtn>
        </div>

        <div className="flex-1 overflow-auto">
          {loading && (
            <div className="flex items-center gap-2 p-6 text-sm text-ink-400">
              <IconSpinner /> Loading…
            </div>
          )}
          {error && <div className="p-6 text-sm text-signal-red">{error}</div>}

          {!loading && tab === "source" && detail && (
            <>
              <div className="flex flex-wrap gap-2 px-5 py-3">
                <span className="badge bg-ink-800 text-ink-300">{detail.kind}</span>
                <span className="badge bg-ink-800 text-ink-300">{detail.tokens} tokens</span>
                {detail.language && (
                  <span className="badge bg-ink-800 text-ink-300">{detail.language}</span>
                )}
              </div>
              <pre className="overflow-x-auto px-5 pb-6 text-[12.5px] leading-relaxed">
                <code className="font-mono text-ink-100">{detail.raw_text}</code>
              </pre>
            </>
          )}

          {!loading && tab === "dependencies" && (
            <div className="space-y-5 p-5">
              <DepList
                title="What depends on this"
                hint="these break if this changes"
                items={neighbors?.dependents ?? []}
                onNavigate={navigate}
                tone="text-signal-amber"
              />
              <DepList
                title="What this depends on"
                hint="this breaks if these change"
                items={neighbors?.depends_on ?? []}
                onNavigate={navigate}
                tone="text-signal-blue"
              />
            </div>
          )}
        </div>

        {detail?.github_url && tab === "source" && (
          <a
            href={detail.github_url}
            target="_blank"
            rel="noreferrer"
            className="btn-ghost m-4 justify-center"
          >
            <IconExternal /> View on GitHub
          </a>
        )}
      </div>
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-t-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
        active
          ? "border-b-2 border-signal-blue text-ink-100"
          : "text-ink-400 hover:text-ink-200"
      }`}
    >
      {children}
    </button>
  );
}

function DepList({
  title,
  hint,
  items,
  onNavigate,
  tone,
}: {
  title: string;
  hint: string;
  items: DependencyNode[];
  onNavigate: (id: string) => void;
  tone: string;
}) {
  return (
    <section>
      <div className="mb-2">
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-300">
          {title} ({items.length})
        </div>
        <div className="text-[11px] text-ink-500">{hint}</div>
      </div>
      {items.length === 0 ? (
        <div className="text-sm text-ink-500">Nothing in the graph.</div>
      ) : (
        <ul className="space-y-1">
          {items.map((a) => (
            <li key={`${a.qualified_name}-${a.edge_kind}`}>
              <button
                onClick={() => a.id && onNavigate(a.id)}
                className="group flex w-full items-center gap-2.5 rounded-lg border border-transparent px-2 py-1.5 text-left hover:border-ink-700 hover:bg-ink-850/60"
              >
                <IconFile className={`shrink-0 text-ink-600 group-hover:${tone}`} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-mono text-[12.5px] text-ink-100">
                    {a.symbol}
                  </span>
                  <span className="block truncate font-mono text-[10px] text-ink-500">
                    {a.path}
                  </span>
                </span>
                <span className="badge shrink-0 bg-ink-800 text-ink-400">{a.edge_kind}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
