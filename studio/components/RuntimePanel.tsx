"use client";

import { useState } from "react";
import {
  candidateCount,
  confidenceOf,
  filesUsed,
} from "@/lib/execution-insights";
import type { Execution, ExecutionEvent } from "@/lib/types";
import { FilesUsed } from "./FilesUsed";
import { TokenReduction } from "./TokenReduction";
import { IconChevron } from "./icons";

const ms = (n?: number) =>
  n == null ? "—" : n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${n}ms`;

const CONFIDENCE_COLOR = {
  High: "text-signal-green",
  Medium: "text-signal-amber",
  Low: "text-signal-red",
} as const;

function Stat({ label, value, mono = true }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/50 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-ink-500">{label}</div>
      <div className={`mt-0.5 text-sm text-ink-100 ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}

// Only meaningful runtime information — the values the directive calls for,
// each read from a real event or metric. No decorative graphs.
export function RuntimePanel({
  execution,
  events,
  baselineTokens,
  baselinePending,
  onRunBaseline,
  onOpenFile,
}: {
  execution: Execution;
  events: ExecutionEvent[];
  baselineTokens: number | null;
  baselinePending: boolean;
  onRunBaseline: () => void;
  onOpenFile: (qualifiedName: string) => void;
}) {
  const m = execution.metrics ?? {};
  const files = filesUsed(events);
  const confidence = confidenceOf(execution);
  const path = m.path ?? "—";
  const [showDecisions, setShowDecisions] = useState(false);

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      {/* path + confidence */}
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-ink-800 bg-ink-900/50 px-3 py-2.5">
          <div className="text-[10px] uppercase tracking-wider text-ink-500">
            Execution path
          </div>
          <div className="mt-1 flex items-center gap-1.5">
            <span
              className={`h-1.5 w-1.5 rounded-full ${path === "fast" ? "bg-signal-cyan" : "bg-signal-violet"}`}
            />
            <span className="text-sm font-medium capitalize text-ink-100">
              {path} {path !== "—" && "path"}
            </span>
          </div>
        </div>
        <div className="rounded-lg border border-ink-800 bg-ink-900/50 px-3 py-2.5">
          <div className="text-[10px] uppercase tracking-wider text-ink-500">
            Confidence
          </div>
          <div
            className={`mt-1 text-sm font-medium ${CONFIDENCE_COLOR[confidence.level]}`}
            title={confidence.reason}
          >
            {confidence.level}
          </div>
        </div>
      </div>

      {/* measured token reduction */}
      <TokenReduction
        metrics={m}
        baselineTokens={baselineTokens}
        baselinePending={baselinePending}
        onRunBaseline={onRunBaseline}
      />

      {/* quick stats */}
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Context selected" value={`${m.artifacts_included ?? files.length} files`} />
        <Stat label="Candidates" value={candidateCount(events)} />
        <Stat label="Latency" value={ms(m.total_ms)} />
        <Stat label="Model calls" value={m.generation_calls ?? "—"} />
      </div>

      {/* files used */}
      {files.length > 0 && (
        <div>
          <div className="mb-2 text-[10px] uppercase tracking-wider text-ink-500">
            Files used ({files.length})
          </div>
          <FilesUsed files={files} onOpen={onOpenFile} compact />
        </div>
      )}

      {/* budget decisions — the inference the runtime chose to skip or spend */}
      {(m.decisions?.length ?? 0) > 0 && (
        <div className="rounded-lg border border-ink-800 bg-ink-900/50">
          <button
            onClick={() => setShowDecisions((v) => !v)}
            className="flex w-full items-center justify-between px-3 py-2 text-[10px] uppercase tracking-wider text-ink-500 hover:text-ink-300"
          >
            Inference budget ({m.decisions!.length})
            <IconChevron className={showDecisions ? "rotate-180" : ""} />
          </button>
          {showDecisions && (
            <ul className="space-y-1.5 px-3 pb-3">
              {m.decisions!.map((d, i) => (
                <li key={i} className="text-[11px]">
                  <span
                    className={`badge mr-1.5 ${
                      d.decision === "SKIP"
                        ? "bg-signal-green/10 text-signal-green"
                        : d.decision === "ESCALATE"
                          ? "bg-signal-amber/10 text-signal-amber"
                          : "bg-signal-blue/10 text-signal-blue"
                    }`}
                  >
                    {d.decision}
                  </span>
                  <span className="font-mono text-ink-300">{d.operation}</span>
                  <div className="mt-0.5 pl-1 text-ink-500">{d.reason}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
