"use client";

// Inference Playground: submit a query in cortex or baseline mode and
// watch every runtime decision stream in live. Session mode keeps
// Semantic Virtual Memory pages resident across questions.

import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import { LiveExecutionEventStream } from "@/lib/eventStream";
import type { Execution, ExecutionEvent, ExecutionMode } from "@/lib/types";
import { EventFeed } from "@/components/EventFeed";
import { MetricBar } from "@/components/MetricBar";

export default function Playground() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<ExecutionMode>("cortex");
  const [sessionOn, setSessionOn] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [execution, setExecution] = useState<Execution | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const run = useCallback(async () => {
    if (!query.trim() || running) return;
    setRunning(true);
    setError(null);
    setEvents([]);
    setExecution(null);
    unsubscribeRef.current?.();

    if (sessionOn && !sessionIdRef.current) {
      sessionIdRef.current = crypto.randomUUID();
    }

    try {
      const { execution_id } = await api.createExecution({
        query,
        mode,
        session_id: sessionOn ? sessionIdRef.current : null,
      });
      const stream = new LiveExecutionEventStream(execution_id);
      unsubscribeRef.current = stream.subscribe(
        (event) => setEvents((prev) => [...prev, event]),
        async () => {
          const final = await api.execution(execution_id);
          setExecution(final);
          setRunning(false);
        },
        (err) => {
          setError(err.message);
          setRunning(false);
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setRunning(false);
    }
  }, [query, mode, sessionOn, running]);

  const metrics = execution?.metrics;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Inference Playground</h1>
        <p className="mt-1 text-sm text-ink-400">
          Ask the ingested repository a question and watch the runtime decide
          what context it actually needs.
        </p>
      </div>

      {/* Controls */}
      <div className="panel p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded border border-ink-600 font-mono text-xs">
            {(["cortex", "baseline"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 uppercase tracking-wider transition-colors ${
                  mode === m
                    ? m === "cortex"
                      ? "bg-signal-blue/20 text-signal-blue"
                      : "bg-signal-amber/20 text-signal-amber"
                    : "text-ink-400 hover:text-ink-200"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <label className="flex cursor-pointer items-center gap-2 font-mono text-xs text-ink-300">
            <input
              type="checkbox"
              checked={sessionOn}
              onChange={(e) => {
                setSessionOn(e.target.checked);
                if (!e.target.checked) sessionIdRef.current = null;
              }}
              className="accent-signal-cyan"
              disabled={mode === "baseline"}
            />
            SVM session
            {sessionOn && sessionIdRef.current && (
              <span className="text-ink-500">
                {sessionIdRef.current.slice(0, 8)}
              </span>
            )}
          </label>
        </div>
        <div className="mt-3 flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder='e.g. "Will changing the session record schema affect payments?"'
            className="flex-1 rounded border border-ink-600 bg-ink-850 px-3 py-2 text-sm outline-none placeholder:text-ink-500 focus:border-signal-blue"
          />
          <button
            onClick={run}
            disabled={running || !query.trim()}
            className="rounded bg-signal-blue px-5 py-2 text-sm font-semibold text-ink-950 transition-opacity disabled:opacity-40"
          >
            {running ? "Running…" : "Execute"}
          </button>
        </div>
        {error && (
          <div className="mt-2 text-xs text-signal-red">{error}</div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* Event feed */}
        <section className="panel lg:col-span-3">
          <div className="panel-header">
            <span className="panel-title">Execution Events</span>
            {running && (
              <span className="badge bg-signal-blue/10 text-signal-blue">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal-blue" />
                live
              </span>
            )}
          </div>
          <div className="p-2">
            {events.length === 0 ? (
              <div className="p-6 text-center text-sm text-ink-500">
                No execution yet.
              </div>
            ) : (
              <EventFeed events={events} />
            )}
          </div>
        </section>

        {/* Answer + metrics */}
        <div className="space-y-4 lg:col-span-2">
          <section className="panel">
            <div className="panel-header">
              <span className="panel-title">Answer</span>
              {execution && (
                <span className="font-mono text-[10px] text-ink-500">
                  {execution.mode}
                </span>
              )}
            </div>
            <div className="p-4 text-sm leading-relaxed text-ink-200">
              {execution?.answer ??
                (running ? "…" : "Execute a query to see the answer.")}
            </div>
          </section>

          {metrics && (
            <section className="panel p-4">
              <div className="panel-title mb-4">Resource Consumption</div>
              <div className="space-y-3">
                <MetricBar
                  label="input tokens"
                  value={metrics.input_tokens ?? 0}
                  max={Math.max(
                    metrics.input_tokens ?? 0,
                    metrics.candidate_tokens ?? 0,
                  )}
                  color="bg-signal-blue"
                />
                {metrics.candidate_tokens != null && (
                  <MetricBar
                    label="retrieved candidates (uncompiled)"
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
                <div className="flex justify-between font-mono text-xs">
                  <span className="text-ink-300">wall time</span>
                  <span>{((metrics.total_ms ?? 0) / 1000).toFixed(1)}s</span>
                </div>
                {metrics.svm && (
                  <div className="border-t border-ink-800 pt-3">
                    <div className="panel-title mb-2 text-signal-cyan">
                      Semantic Virtual Memory
                    </div>
                    <div className="grid grid-cols-2 gap-2 font-mono text-xs text-ink-300">
                      <span>pages resident</span>
                      <span className="text-right">{metrics.svm.resident_pages}</span>
                      <span>pages reused</span>
                      <span className="text-right text-signal-green">
                        {metrics.svm.pages_reused}
                      </span>
                      <span>page faults</span>
                      <span className="text-right text-signal-amber">
                        {metrics.svm.pages_faulted_in}
                      </span>
                      <span>resident tokens</span>
                      <span className="text-right">{metrics.svm.resident_tokens}</span>
                    </div>
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
