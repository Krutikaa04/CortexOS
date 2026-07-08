"use client";

// Benchmark report: mode summaries, headline comparison, per-question
// breakdown with links to each execution's Context X-Ray.

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type { BenchmarkRun } from "@/lib/types";
import { MetricBar } from "@/components/MetricBar";

export default function BenchmarkDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api.benchmark(id).then(setRun).catch((e) => setError(String(e)));
    load();
    const interval = setInterval(() => {
      // poll while running
      api.benchmark(id).then((r) => {
        setRun(r);
        if (r.status !== "running") clearInterval(interval);
      });
    }, 10_000);
    return () => clearInterval(interval);
  }, [id]);

  if (error) return <div className="panel p-4 text-sm text-signal-red">{error}</div>;
  if (!run) return <div className="text-sm text-ink-500">loading…</div>;

  const report = run.report;
  const cmp = report?.summary?.comparison;
  const base = report?.summary?.baseline;
  const cortex = report?.summary?.cortex;
  const maxTokens = Math.max(
    base?.mean_input_tokens ?? 0,
    cortex?.mean_input_tokens ?? 0,
  );

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">{run.name}</h1>
          <span
            className={`badge ${
              run.status === "succeeded"
                ? "bg-signal-green/10 text-signal-green"
                : run.status === "running"
                  ? "bg-signal-blue/10 text-signal-blue"
                  : "bg-signal-red/10 text-signal-red"
            }`}
          >
            {run.status}
          </span>
        </div>
        {report && (
          <p className="mt-1 font-mono text-xs text-ink-500">
            {report.question_count} questions · task model{" "}
            {report.models.task_model} · embeddings {report.models.embed_model}
          </p>
        )}
      </div>

      {run.status === "running" && (
        <div className="panel p-4 text-sm text-signal-blue">
          Benchmark in progress — executions are running on the local model.
          This page refreshes automatically.
        </div>
      )}
      {run.error && (
        <div className="panel p-4 text-sm text-signal-red">{run.error}</div>
      )}

      {cmp && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="panel p-5">
            <div className="stat-label">Input-token reduction</div>
            <div className="stat-value mt-2 text-signal-green">
              −{cmp.input_token_reduction_pct}%
            </div>
          </div>
          <div className="panel p-5">
            <div className="stat-label">Quality retention</div>
            <div className="stat-value mt-2 text-signal-blue">
              {cmp.quality_retention_pct != null
                ? `${cmp.quality_retention_pct}%`
                : "—"}
            </div>
          </div>
          <div className="panel p-5">
            <div className="stat-label">Latency ratio</div>
            <div className="stat-value mt-2">
              {cmp.latency_ratio != null ? `${cmp.latency_ratio}×` : "—"}
            </div>
          </div>
        </div>
      )}

      {base && cortex && (
        <section className="panel p-5">
          <div className="panel-title mb-4">Mean input tokens per question</div>
          <div className="space-y-3">
            <MetricBar
              label={`baseline top-K RAG (quality ${base.mean_quality})`}
              value={base.mean_input_tokens ?? 0}
              max={maxTokens}
              color="bg-signal-amber"
            />
            <MetricBar
              label={`CortexOS compiled context (quality ${cortex.mean_quality})`}
              value={cortex.mean_input_tokens ?? 0}
              max={maxTokens}
              color="bg-signal-blue"
            />
          </div>
        </section>
      )}

      {report?.per_question && (
        <section className="panel overflow-x-auto">
          <div className="panel-header">
            <span className="panel-title">Per-question results</span>
          </div>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-700 text-[11px] uppercase tracking-wider text-ink-400">
                <th className="px-4 py-2.5">Q</th>
                <th className="px-4 py-2.5">Category</th>
                <th className="px-4 py-2.5 text-right">Baseline tok / quality</th>
                <th className="px-4 py-2.5 text-right">Cortex tok / quality</th>
                <th className="px-4 py-2.5 text-right">Δ tokens</th>
                <th className="px-4 py-2.5 text-right">X-Ray</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-800 font-mono text-xs">
              {report.per_question.map((q) => {
                const b = q.baseline;
                const c = q.cortex;
                const delta =
                  b?.input_tokens != null && c?.input_tokens != null
                    ? 100 * (1 - c.input_tokens / b.input_tokens)
                    : null;
                return (
                  <tr key={q.id} className="hover:bg-ink-850">
                    <td className="px-4 py-2.5 text-ink-300">{q.id}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`badge ${
                          q.category === "multi_hop"
                            ? "bg-signal-violet/10 text-signal-violet"
                            : q.category === "structural"
                              ? "bg-signal-cyan/10 text-signal-cyan"
                              : "bg-ink-700 text-ink-300"
                        }`}
                      >
                        {q.category}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {b?.error
                        ? "failed"
                        : `${b?.input_tokens ?? "—"} / ${b?.quality ?? "—"}`}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {c?.error
                        ? "failed"
                        : `${c?.input_tokens ?? "—"} / ${c?.quality ?? "—"}`}
                    </td>
                    <td
                      className={`px-4 py-2.5 text-right ${
                        delta != null && delta > 0
                          ? "text-signal-green"
                          : "text-signal-red"
                      }`}
                    >
                      {delta != null ? `−${delta.toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {c?.execution_id && (
                        <Link
                          href={`/executions/${c.execution_id}`}
                          className="text-signal-blue hover:underline"
                        >
                          view
                        </Link>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
