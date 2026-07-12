"use client";

import { STAGES, currentStageIndex } from "@/lib/execution-insights";
import type { ExecutionEvent } from "@/lib/types";
import { IconCheck, IconSpinner } from "./icons";

// The four canonical stages every question moves through, shown as a live
// checklist. Fast-path questions skip straight through the early stages;
// the labels are the same ones the runtime actually reports.
export function StageIndicator({ events }: { events: ExecutionEvent[] }) {
  const idx = currentStageIndex(events);
  return (
    <div className="panel animate-fade-up p-4">
      <ul className="space-y-2.5">
        {STAGES.map((stage, i) => {
          const done = i < idx;
          const active = i === idx;
          return (
            <li key={stage.key} className="flex items-center gap-3 text-sm">
              <span className="flex h-5 w-5 items-center justify-center">
                {done ? (
                  <IconCheck className="text-signal-green" />
                ) : active ? (
                  <IconSpinner className="text-signal-blue" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-ink-700" />
                )}
              </span>
              <span
                className={
                  done
                    ? "text-ink-400"
                    : active
                      ? "font-medium text-ink-100"
                      : "text-ink-600"
                }
              >
                {stage.label}
                {active ? "…" : ""}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
