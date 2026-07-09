"use client";

// Inference Playground: ask a question, get the answer plus proof of what
// it cost. By default every question runs through BOTH CortexOS and a
// conventional RAG pipeline on the same local models, so the savings shown
// are real measurements — not estimates. Runtime decision details are one
// click away for those who want them.

import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import { LiveExecutionEventStream } from "@/lib/eventStream";
import type { Execution, ExecutionEvent } from "@/lib/types";
import { EventFeed } from "@/components/EventFeed";
import { SavingsCard } from "@/components/SavingsCard";

const BASELINE_POLL_MS = 5_000;
const BASELINE_TIMEOUT_MS = 10 * 60_000;

export default function Playground() {
  const [query, setQuery] = useState("");
  const [compare, setCompare] = useState(true);
  const [sessionOn, setSessionOn] = useState(false);
  const sessionIdRef = useRef<string | null>(null);

  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [execution, setExecution] = useState<Execution | null>(null);
  const [baselineTokens, setBaselineTokens] = useState<number | null>(null);
  const [baselinePending, setBaselinePending] = useState(false);
  const [running, setRunning] = useState(false);
  const [showDecisions, setShowDecisions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unsubscribeRef = useRef<(() => void) | null>(null);
  const baselineTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollBaseline = useCallback((baselineId: string) => {
    if (baselineTimerRef.current) clearInterval(baselineTimerRef.current);
    setBaselinePending(true);
    const startedAt = Date.now();
    baselineTimerRef.current = setInterval(async () => {
      try {
        const b = await api.execution(baselineId);
        if (b.status === "succeeded") {
          setBaselineTokens(b.metrics?.input_tokens ?? null);
          setBaselinePending(false);
          clearInterval(baselineTimerRef.current!);
        } else if (
          b.status === "failed" ||
          Date.now() - startedAt > BASELINE_TIMEOUT_MS
        ) {
          setBaselinePending(false);
          clearInterval(baselineTimerRef.current!);
        }
      } catch {
        /* transient — keep polling until timeout */
      }
    }, BASELINE_POLL_MS);
  }, []);

  const run = useCallback(async () => {
    if (!query.trim() || running) return;
    setRunning(true);
    setError(null);
    setEvents([]);
    setExecution(null);
    setBaselineTokens(null);
    setBaselinePending(false);
    unsubscribeRef.current?.();

    if (sessionOn && !sessionIdRef.current) {
      sessionIdRef.current = crypto.randomUUID();
    }

    try {
      // CortexOS execution (streamed live)
      const { execution_id } = await api.createExecution({
        query,
        mode: "cortex",
        session_id: sessionOn ? sessionIdRef.current : null,
      });

      // Comparison execution through the conventional pipeline (background)
      if (compare) {
        api
          .createExecution({ query, mode: "baseline" })
          .then(({ execution_id: baselineId }) => pollBaseline(baselineId))
          .catch(() => setBaselinePending(false));
      }

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
  }, [query, compare, sessionOn, running, pollBaseline]);

  const metrics = execution?.metrics;
  const stage = events.length
    ? events[events.length - 1].event_type
    : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="text-center">
        <h1 className="text-xl font-semibold">Ask the repository</h1>
        <p className="mt-1 text-sm text-ink-400">
          Every answer comes with proof of how few tokens it needed.
        </p>
      </div>

      {/* Question input */}
      <div className="panel p-4">
        <div className="flex gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder='e.g. "Will changing the session schema affect payments?"'
            className="flex-1 rounded border border-ink-600 bg-ink-850 px-3 py-2.5 text-sm outline-none placeholder:text-ink-500 focus:border-signal-blue"
          />
          <button
            onClick={run}
            disabled={running || !query.trim()}
            className="rounded bg-signal-blue px-5 py-2.5 text-sm font-semibold text-ink-950 transition-opacity disabled:opacity-40"
          >
            {running ? "Thinking…" : "Ask"}
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-ink-400">
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={compare}
              onChange={(e) => setCompare(e.target.checked)}
              className="accent-signal-green"
            />
            Compare against conventional RAG (proves the savings)
          </label>
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="checkbox"
              checked={sessionOn}
              onChange={(e) => {
                setSessionOn(e.target.checked);
                if (!e.target.checked) sessionIdRef.current = null;
              }}
              className="accent-signal-cyan"
            />
            Memory session (pages stay resident across questions)
          </label>
        </div>
        {error && <div className="mt-2 text-xs text-signal-red">{error}</div>}
      </div>

      {/* Live progress while running */}
      {running && !execution && (
        <div className="panel flex items-center gap-3 p-4 text-sm text-ink-300">
          <span className="h-2 w-2 animate-pulse rounded-full bg-signal-blue" />
          {stageLabel(stage)}
        </div>
      )}

      {/* Answer */}
      {execution && (
        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">Answer</span>
            {execution.metrics?.svm && (
              <span className="badge bg-signal-cyan/10 text-signal-cyan">
                {execution.metrics.svm.pages_reused} pages reused ·{" "}
                {execution.metrics.svm.pages_faulted_in} loaded
              </span>
            )}
          </div>
          <div className="p-5 text-[15px] leading-relaxed text-ink-100">
            {execution.answer ?? execution.failure_reason}
          </div>
        </section>
      )}

      {/* Savings — the headline of every answer */}
      {execution && metrics?.input_tokens != null && (
        <SavingsCard
          cortexTokens={metrics.input_tokens}
          baselineTokens={baselineTokens}
          baselinePending={baselinePending}
        />
      )}

      {/* Runtime decisions, tucked away by default */}
      {events.length > 0 && (
        <div>
          <button
            onClick={() => setShowDecisions((s) => !s)}
            className="mx-auto block text-xs text-ink-400 underline-offset-4 hover:text-signal-blue hover:underline"
          >
            {showDecisions
              ? "Hide runtime decisions"
              : `Show runtime decisions (${events.length} events — what was kept, what was rejected, and why)`}
          </button>
          {showDecisions && (
            <div className="panel mt-3 p-2">
              <EventFeed events={events} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function stageLabel(stage: string | null): string {
  switch (stage) {
    case null:
    case "TASK_RECEIVED":
      return "Understanding the question…";
    case "TASK_PROFILED":
    case "REQUIREMENTS_CREATED":
      return "Working out what information is needed…";
    case "RETRIEVAL_STARTED":
    case "CANDIDATE_FOUND":
      return "Searching the repository…";
    case "CANDIDATE_REJECTED":
    case "CONTEXT_COMPILED":
      return "Compiling the minimum sufficient context…";
    case "MODEL_SELECTED":
    case "INFERENCE_STARTED":
      return "Generating the answer on the local model…";
    case "PAGE_FAULT":
    case "PAGE_IN":
      return "Loading memory pages…";
    case "SUFFICIENCY_CHECKED":
    case "ESCALATION_TRIGGERED":
      return "Checking the answer is sufficient…";
    default:
      return "Working…";
  }
}
