"use client";

// Public replay demo: real recorded execution traces, replayed through
// the same event-feed components used for live executions. The REPLAY
// badge makes the distinction explicit — recorded and live executions
// must always be visibly distinguishable.

import { useCallback, useEffect, useRef, useState } from "react";
import { RecordedExecutionEventStream } from "@/lib/eventStream";
import type { ExecutionEvent, ExecutionMetrics } from "@/lib/types";
import { EventFeed } from "@/components/EventFeed";
import { MetricBar } from "@/components/MetricBar";

interface RecordedTrace {
  execution: {
    id: string;
    mode: string;
    query: string;
    answer: string | null;
    status: string;
    metrics: ExecutionMetrics;
    source: { display_name: string; commit_sha: string };
  };
  events: ExecutionEvent[];
}

interface TraceBundle {
  title: string;
  exported_at: string;
  traces: RecordedTrace[];
}

export default function DemoPage() {
  const [bundle, setBundle] = useState<TraceBundle | null>(null);
  const [selected, setSelected] = useState(0);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [playing, setPlaying] = useState(false);
  const [finished, setFinished] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    fetch("/traces/demo.json")
      .then((r) => (r.ok ? r.json() : null))
      .then(setBundle)
      .catch(() => setBundle(null));
    return () => unsubscribeRef.current?.();
  }, []);

  const play = useCallback(
    (index: number) => {
      if (!bundle) return;
      unsubscribeRef.current?.();
      setSelected(index);
      setEvents([]);
      setFinished(false);
      setPlaying(true);
      const trace = bundle.traces[index];
      const stream = new RecordedExecutionEventStream(
        trace.events,
        trace.execution.status,
      );
      unsubscribeRef.current = stream.subscribe(
        (event) => setEvents((prev) => [...prev, event]),
        () => {
          setPlaying(false);
          setFinished(true);
        },
      );
    },
    [bundle],
  );

  if (bundle === null) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-semibold">Execution Replay</h1>
        <div className="panel p-6 text-sm text-ink-400">
          No recorded traces bundled yet. Traces are exported from real
          CortexOS executions with{" "}
          <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-xs">
            cortex.traces.export_trace_bundle
          </code>{" "}
          and placed in <span className="font-mono">public/traces/demo.json</span>.
        </div>
      </div>
    );
  }

  const trace = bundle.traces[selected];
  const metrics = trace.execution.metrics;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Execution Replay</h1>
          <span className="badge bg-signal-violet/10 text-signal-violet">
            ● REPLAY — recorded from a real execution
          </span>
        </div>
        <p className="mt-1 text-sm text-ink-400">
          {bundle.title} · repository {trace.execution.source.display_name} @{" "}
          <span className="font-mono">
            {trace.execution.source.commit_sha.slice(0, 10)}
          </span>
        </p>
      </div>

      {/* Trace selector */}
      <div className="flex flex-wrap gap-2">
        {bundle.traces.map((t, i) => (
          <button
            key={t.execution.id}
            onClick={() => play(i)}
            className={`rounded border px-3 py-2 text-left text-xs transition-colors ${
              i === selected
                ? "border-signal-violet bg-signal-violet/10 text-ink-100"
                : "border-ink-700 bg-ink-900 text-ink-300 hover:border-ink-500"
            }`}
          >
            <span
              className={`mr-2 font-mono uppercase ${
                t.execution.mode === "cortex"
                  ? "text-signal-blue"
                  : "text-signal-amber"
              }`}
            >
              {t.execution.mode}
            </span>
            {t.execution.query}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <section className="panel lg:col-span-3">
          <div className="panel-header">
            <span className="panel-title">Recorded Events</span>
            {playing && (
              <span className="badge bg-signal-violet/10 text-signal-violet">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal-violet" />
                replaying
              </span>
            )}
          </div>
          <div className="p-2">
            {events.length === 0 ? (
              <div className="p-6 text-center text-sm text-ink-500">
                Select a trace above to replay it.
              </div>
            ) : (
              <EventFeed events={events} />
            )}
          </div>
        </section>

        <div className="space-y-4 lg:col-span-2">
          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Answer</span>
            </div>
            <div className="p-4 text-sm leading-relaxed text-ink-200">
              {finished ? (trace.execution.answer ?? "—") : playing ? "…" : "—"}
            </div>
          </section>

          {finished && (
            <section className="panel p-4">
              <div className="panel-title mb-4">Measured Consumption</div>
              <div className="space-y-3">
                <MetricBar
                  label="input tokens"
                  value={metrics.input_tokens ?? 0}
                  max={Math.max(
                    metrics.input_tokens ?? 0,
                    metrics.candidate_tokens ?? 0,
                  )}
                />
                {metrics.candidate_tokens != null && (
                  <MetricBar
                    label="uncompiled candidates"
                    value={metrics.candidate_tokens}
                    max={Math.max(
                      metrics.input_tokens ?? 0,
                      metrics.candidate_tokens,
                    )}
                    color="bg-ink-500"
                  />
                )}
                {metrics.context_reduction_pct != null && (
                  <div className="flex justify-between border-t border-ink-800 pt-3 font-mono text-xs">
                    <span className="text-ink-300">context reduction</span>
                    <span className="text-signal-green">
                      −{metrics.context_reduction_pct}%
                    </span>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
