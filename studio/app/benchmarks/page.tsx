"use client";

// Benchmark Lab: run suites, browse results. Every number comes from a
// real paired run — same snapshot, same models, same questions.

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BenchmarkSummary } from "@/lib/types";

export default function BenchmarksPage() {
  const [runs, setRuns] = useState<BenchmarkSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [launching, setLaunching] = useState(false);

  const load = () => {
    api.benchmarks().then(setRuns).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  const launch = async () => {
    setLaunching(true);
    try {
      await api.runBenchmark("demo_store");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Benchmark Lab</h1>
          <p className="mt-1 text-sm text-ink-400">
            CortexOS vs conventional top-K RAG. Paired questions, same
            snapshot, same models — no fabricated numbers.
          </p>
        </div>
        <button
          onClick={launch}
          disabled={launching}
          className="rounded bg-signal-blue px-4 py-2 text-sm font-semibold text-ink-950 disabled:opacity-40"
        >
          {launching ? "Launching…" : "Run demo suite"}
        </button>
      </div>

      {error && <div className="panel p-4 text-sm text-signal-red">{error}</div>}

      <section className="panel overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ink-700 text-[11px] uppercase tracking-wider text-ink-400">
              <th className="px-4 py-2.5">Suite</th>
              <th className="px-4 py-2.5">Started</th>
              <th className="px-4 py-2.5 text-right">Token reduction</th>
              <th className="px-4 py-2.5 text-right">Quality retention</th>
              <th className="px-4 py-2.5 text-right">Latency ratio</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-800 font-mono text-xs">
            {runs?.map((r) => (
              <tr key={r.id} className="hover:bg-ink-850">
                <td className="px-4 py-2.5">
                  <Link
                    href={`/benchmarks/${r.id}`}
                    className="text-ink-200 hover:text-signal-blue"
                  >
                    {r.name}
                  </Link>
                </td>
                <td className="px-4 py-2.5 text-ink-400">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 text-right text-signal-green">
                  {r.summary?.comparison
                    ? `−${r.summary.comparison.input_token_reduction_pct}%`
                    : "—"}
                </td>
                <td className="px-4 py-2.5 text-right text-signal-blue">
                  {r.summary?.comparison?.quality_retention_pct != null
                    ? `${r.summary.comparison.quality_retention_pct}%`
                    : "—"}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {r.summary?.comparison?.latency_ratio != null
                    ? `${r.summary.comparison.latency_ratio}×`
                    : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`badge ${
                      r.status === "succeeded"
                        ? "bg-signal-green/10 text-signal-green"
                        : r.status === "running"
                          ? "bg-signal-blue/10 text-signal-blue"
                          : "bg-signal-red/10 text-signal-red"
                    }`}
                  >
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
            {runs?.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-ink-500">
                  No benchmark runs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
