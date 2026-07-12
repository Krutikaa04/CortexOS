"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ArtifactDetail } from "@/lib/types";
import { CopyButton } from "./CodeBlock";
import { IconClose, IconExternal, IconGitHub, IconSpinner } from "./icons";

export interface ArtifactTarget {
  versionId: string;
  artifactId?: string;
  qualifiedName?: string;
}

export function ArtifactDrawer({
  target,
  onClose,
}: {
  target: ArtifactTarget | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<ArtifactDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    let active = true;
    setDetail(null);
    setError(null);
    setLoading(true);
    (async () => {
      try {
        let id = target.artifactId;
        if (!id && target.qualifiedName) {
          const ref = await api.lookup(target.versionId, target.qualifiedName);
          id = ref.id;
        }
        if (!id) throw new Error("artifact not found");
        const d = await api.artifact(target.versionId, id);
        if (active) setDetail(d);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [target]);

  if (!target) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="animate-fade-up relative flex h-full w-full max-w-2xl flex-col border-l border-ink-800 bg-ink-950 shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-ink-800 px-5 py-3.5">
          <div className="min-w-0">
            <div className="truncate font-mono text-sm text-ink-100">
              {detail?.qualified_name.split("::").pop() ??
                target.qualifiedName?.split("::").pop() ??
                "Artifact"}
            </div>
            <div className="mt-0.5 truncate font-mono text-[11px] text-ink-500">
              {detail?.path ?? target.qualifiedName?.split("::")[0]}
              {detail && ` · L${detail.span_start_line}–${detail.span_end_line}`}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {detail && <CopyButton text={detail.raw_text} label="Copy source" />}
            {detail?.github_url && (
              <a
                href={detail.github_url}
                target="_blank"
                rel="noreferrer"
                className="btn-icon"
                title="Open on GitHub"
              >
                <IconGitHub />
              </a>
            )}
            <button onClick={onClose} className="btn-icon" title="Close">
              <IconClose />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          {loading && (
            <div className="flex items-center gap-2 p-6 text-sm text-ink-400">
              <IconSpinner /> Loading source…
            </div>
          )}
          {error && <div className="p-6 text-sm text-signal-red">{error}</div>}
          {detail && (
            <>
              <div className="flex flex-wrap gap-2 px-5 py-3">
                <span className="badge bg-ink-800 text-ink-300">{detail.kind}</span>
                <span className="badge bg-ink-800 text-ink-300">
                  {detail.tokens} tokens
                </span>
                {detail.language && (
                  <span className="badge bg-ink-800 text-ink-300">
                    {detail.language}
                  </span>
                )}
              </div>
              <pre className="overflow-x-auto px-5 pb-6 text-[12.5px] leading-relaxed">
                <code className="font-mono text-ink-100">{detail.raw_text}</code>
              </pre>
            </>
          )}
        </div>

        {detail?.github_url && (
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
