"use client";

// Context X-Ray: the full decision trace of one execution — what was
// available, what was selected at which representation, what was rejected
// and WHY, and what it cost.

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { Execution, ExecutionEvent } from "@/lib/types";
import { EventFeed } from "@/components/EventFeed";

interface IncludedArtifact {
  qualified_name: string;
  representation: string;
  tokens: number;
}

interface RejectedArtifact {
  qualified_name: string;
  reason: string;
  tokens_saved: number;
  detail?: string;
}

export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const [execution, setExecution] = useState<Execution | null>(null);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.execution(id), api.executionEvents(id)])
      .then(([e, ev]) => {
        setExecution(e);
        setEvents(ev);
      })
      .catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="panel p-4 text-sm text-signal-red">{error}</div>;
  if (!execution) return <div className="text-sm text-ink-500">loading…</div>;

  const compiled = events.find((e) => e.event_type === "CONTEXT_COMPILED")
    ?.payload as
    | { included: IncludedArtifact[]; compiled_tokens: number; candidate_tokens: number; reduction_pct: number; budget: number }
    | undefined;
  const rejections = events
    .filter((e) => e.event_type === "CANDIDATE_REJECTED")
    .map((e) => e.payload as unknown as RejectedArtifact);
  const requirements = events.find(
    (e) => e.event_type === "REQUIREMENTS_CREATED",
  )?.payload as { requirements?: { id: string; description: string }[] } | undefined;

  const reprColor: Record<string, string> = {
    raw: "text-signal-blue",
    summary: "text-signal-violet",
    facts: "text-signal-cyan",
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Context X-Ray</h1>
          <span
            className={`badge ${
              execution.mode === "cortex"
                ? "bg-signal-blue/10 text-signal-blue"
                : "bg-signal-amber/10 text-signal-amber"
            }`}
          >
            {execution.mode}
          </span>
        </div>
        <p className="mt-1 font-mono text-sm text-ink-300">“{execution.query}”</p>
      </div>

      {/* Compilation summary */}
      {compiled && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="panel p-4">
            <div className="stat-label">candidates</div>
            <div className="stat-value mt-1 text-ink-300">
              {compiled.candidate_tokens.toLocaleString()}
              <span className="ml-1 text-xs text-ink-500">tok</span>
            </div>
          </div>
          <div className="panel p-4">
            <div className="stat-label">compiled</div>
            <div className="stat-value mt-1 text-signal-blue">
              {compiled.compiled_tokens.toLocaleString()}
              <span className="ml-1 text-xs text-ink-500">tok</span>
            </div>
          </div>
          <div className="panel p-4">
            <div className="stat-label">reduction</div>
            <div className="stat-value mt-1 text-signal-green">
              −{compiled.reduction_pct}%
            </div>
          </div>
          <div className="panel p-4">
            <div className="stat-label">budget</div>
            <div className="stat-value mt-1">{compiled.budget.toLocaleString()}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Requirements + included */}
        <div className="space-y-4">
          {requirements?.requirements && (
            <section className="panel">
              <div className="panel-header">
                <span className="panel-title">Information Requirements</span>
              </div>
              <div className="divide-y divide-ink-800">
                {requirements.requirements.map((r) => (
                  <div key={r.id} className="flex gap-3 p-3 text-sm">
                    <span className="font-mono text-xs text-signal-blue">{r.id}</span>
                    <span className="text-ink-200">{r.description}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Included in Context</span>
              <span className="font-mono text-[10px] text-ink-500">
                {compiled?.included.length ?? 0} artifacts
              </span>
            </div>
            <div className="divide-y divide-ink-800">
              {compiled?.included.map((a) => (
                <div
                  key={a.qualified_name}
                  className="flex items-center justify-between p-3 font-mono text-xs"
                >
                  <span className="truncate text-ink-200">{a.qualified_name}</span>
                  <span className="flex shrink-0 items-center gap-3">
                    <span className={reprColor[a.representation] ?? "text-ink-400"}>
                      {a.representation}
                    </span>
                    <span className="text-ink-400">{a.tokens} tok</span>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Rejected — with reasons</span>
              <span className="font-mono text-[10px] text-ink-500">
                {rejections.length} artifacts
              </span>
            </div>
            <div className="max-h-72 divide-y divide-ink-800 overflow-y-auto">
              {rejections.map((r, i) => (
                <div key={i} className="p-3 font-mono text-xs">
                  <div className="flex items-center justify-between">
                    <span className="truncate text-ink-300">{r.qualified_name}</span>
                    <span className="shrink-0 text-signal-amber">{r.reason}</span>
                  </div>
                  {r.detail && (
                    <div className="mt-0.5 text-[11px] text-ink-500">{r.detail}</div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Answer + full event timeline */}
        <div className="space-y-4">
          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Answer</span>
            </div>
            <div className="p-4 text-sm leading-relaxed text-ink-200">
              {execution.answer ?? execution.failure_reason ?? "—"}
            </div>
          </section>
          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Full Event Timeline</span>
              <span className="font-mono text-[10px] text-ink-500">
                {events.length} events
              </span>
            </div>
            <div className="p-2">
              <EventFeed events={events} />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
