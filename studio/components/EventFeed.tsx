"use client";

// Live/replayed execution event feed — the runtime's decisions as they
// happen. Consumes the shared ExecutionEventStream contract.

import { useEffect, useRef } from "react";
import type { ExecutionEvent } from "@/lib/types";

const EVENT_STYLES: Record<string, { color: string; icon: string }> = {
  TASK_RECEIVED: { color: "text-ink-200", icon: "▸" },
  TASK_PROFILED: { color: "text-signal-blue", icon: "◈" },
  REQUIREMENTS_CREATED: { color: "text-signal-blue", icon: "☰" },
  RETRIEVAL_STARTED: { color: "text-ink-300", icon: "⌕" },
  CANDIDATE_FOUND: { color: "text-ink-400", icon: "+" },
  CANDIDATE_REJECTED: { color: "text-signal-amber", icon: "−" },
  CONTEXT_COMPILED: { color: "text-signal-cyan", icon: "⚙" },
  MODEL_SELECTED: { color: "text-signal-violet", icon: "◉" },
  INFERENCE_STARTED: { color: "text-ink-300", icon: "…" },
  INFERENCE_COMPLETED: { color: "text-signal-green", icon: "✓" },
  PAGE_FAULT: { color: "text-signal-amber", icon: "⚠" },
  PAGE_IN: { color: "text-signal-cyan", icon: "⇥" },
  EVICT: { color: "text-signal-red", icon: "⇤" },
  INVALIDATE: { color: "text-signal-red", icon: "✕" },
  SUFFICIENCY_CHECKED: { color: "text-signal-blue", icon: "?" },
  ESCALATION_TRIGGERED: { color: "text-signal-amber", icon: "↑" },
  EXECUTION_COMPLETED: { color: "text-signal-green", icon: "■" },
  EXECUTION_FAILED: { color: "text-signal-red", icon: "■" },
};

function summarize(event: ExecutionEvent): string {
  const p = event.payload as Record<string, any>;
  switch (event.event_type) {
    case "TASK_RECEIVED":
      return `${p.mode} · "${p.query}"`;
    case "TASK_PROFILED":
      return `${p.task_type} · budget ${p.context_budget_tokens} tok · depth ${p.dependency_depth}`;
    case "REQUIREMENTS_CREATED":
      return `${(p.requirements ?? []).length} requirements (${p.strategy})`;
    case "RETRIEVAL_STARTED":
      return `${p.strategy}${p.round ? ` · round ${p.round}` : ""}`;
    case "CANDIDATE_FOUND":
      return `${p.qualified_name ?? p.path} · score ${p.score ?? p.similarity}`;
    case "CANDIDATE_REJECTED":
      return `${p.qualified_name} · ${p.reason} (−${p.tokens_saved} tok)`;
    case "CONTEXT_COMPILED":
      return `${p.compiled_tokens}/${p.candidate_tokens} tok · −${p.reduction_pct}%`;
    case "MODEL_SELECTED":
      return p.model;
    case "INFERENCE_COMPLETED":
      return `${p.input_tokens} in / ${p.output_tokens} out · ${(p.duration_ms / 1000).toFixed(1)}s`;
    case "PAGE_FAULT":
      return p.qualified_name;
    case "PAGE_IN":
      return `${p.qualified_name} · ${p.representation} · ${p.tokens} tok · seq ${p.seq}`;
    case "EVICT":
      return `${p.qualified_name} · freed ${p.tokens} tok`;
    case "SUFFICIENCY_CHECKED":
      return p.sufficient
        ? `sufficient · coverage ${p.requirement_coverage}`
        : `insufficient: ${(p.reasons ?? []).join(", ")}`;
    case "ESCALATION_TRIGGERED":
      return `expand → budget ${p.new_budget}, top-k ${p.new_top_k}`;
    case "EXECUTION_COMPLETED":
      return `done · ${p.metrics?.input_tokens} input tokens`;
    case "EXECUTION_FAILED":
      return p.error;
    default:
      return "";
  }
}

export function EventFeed({ events }: { events: ExecutionEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [events.length]);

  return (
    <div className="max-h-[28rem] space-y-0.5 overflow-y-auto font-mono text-xs">
      {events.map((event) => {
        const style = EVENT_STYLES[event.event_type] ?? {
          color: "text-ink-400",
          icon: "·",
        };
        return (
          <div
            key={event.seq}
            className="flex items-start gap-2 rounded px-2 py-1 hover:bg-ink-850"
          >
            <span className={`w-4 shrink-0 text-center ${style.color}`}>
              {style.icon}
            </span>
            <span className={`w-44 shrink-0 ${style.color}`}>
              {event.event_type}
            </span>
            <span className="break-all text-ink-300">{summarize(event)}</span>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
