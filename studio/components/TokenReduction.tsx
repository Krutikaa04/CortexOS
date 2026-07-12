"use client";

import type { ExecutionMetrics } from "@/lib/types";
import { IconSpinner } from "./icons";

const fmt = (n: number) => n.toLocaleString("en-US");

function Bar({
  label,
  value,
  max,
  color,
  muted,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
  muted?: boolean;
}) {
  const pct = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className={`text-[11px] ${muted ? "text-ink-500" : "text-ink-300"}`}>
          {label}
        </span>
        <span className="font-mono text-xs text-ink-200">{fmt(value)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ink-850">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// Every CortexOS run instantly measures retrieved-candidate tokens vs the
// compiled context it actually sent. The true baseline-vs-CortexOS figure
// requires a second full pipeline run, offered on demand — never estimated.
export function TokenReduction({
  metrics,
  baselineTokens,
  baselinePending,
  onRunBaseline,
}: {
  metrics: ExecutionMetrics;
  baselineTokens: number | null;
  baselinePending: boolean;
  onRunBaseline?: () => void;
}) {
  const cortex = metrics.input_tokens ?? metrics.context_tokens_sent ?? 0;
  const candidate = metrics.candidate_tokens ?? 0;
  const compiledReduction =
    metrics.context_reduction_pct ??
    (candidate > 0 ? Math.round((1 - cortex / candidate) * 1000) / 10 : 0);

  const baselineReduction =
    baselineTokens && baselineTokens > 0
      ? Math.round((1 - cortex / baselineTokens) * 1000) / 10
      : null;

  // Headline uses the true baseline when measured, else the always-measured
  // retrieved→compiled reduction.
  const headline = baselineReduction ?? compiledReduction;
  const headlineLabel = baselineReduction != null
    ? "vs conventional RAG baseline"
    : "retrieved → compiled context";
  const barMax = Math.max(baselineTokens ?? 0, candidate, cortex);

  return (
    <div className="panel p-4">
      <div className="flex items-baseline justify-between">
        <span className="stat-label">Token reduction</span>
        <span className="badge bg-signal-green/10 text-signal-green">measured</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="font-mono text-3xl font-semibold text-signal-green">
          {headline}%
        </span>
      </div>
      <div className="mb-3 text-[11px] text-ink-500">{headlineLabel}</div>

      <div className="space-y-2.5">
        {baselineTokens != null && (
          <Bar
            label="Baseline (conventional RAG)"
            value={baselineTokens}
            max={barMax}
            color="bg-ink-500"
            muted
          />
        )}
        {candidate > 0 && (
          <Bar
            label="Retrieved candidates"
            value={candidate}
            max={barMax}
            color="bg-ink-600"
            muted
          />
        )}
        <Bar
          label="CortexOS (sent to model)"
          value={cortex}
          max={barMax}
          color="bg-signal-green"
        />
      </div>

      {baselineTokens == null && onRunBaseline && (
        <button
          onClick={onRunBaseline}
          disabled={baselinePending}
          className="btn-ghost mt-3 w-full justify-center text-xs"
        >
          {baselinePending ? (
            <>
              <IconSpinner /> Running baseline pipeline…
            </>
          ) : (
            "Run baseline comparison"
          )}
        </button>
      )}
    </div>
  );
}
