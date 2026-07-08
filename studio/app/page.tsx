"use client";

// Command Center: system health, knowledge sources, latest benchmark
// comparison, recent executions. Every number on this screen comes from
// real runtime state — nothing is fabricated.

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BenchmarkSummary, SourceSummary } from "@/lib/types";

export default function CommandCenter() {
  const [sources, setSources] = useState<SourceSummary[] | null>(null);
  const [benchmarks, setBenchmarks] = useState<BenchmarkSummary[] | null>(null);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    Promise.all([api.sources(), api.benchmarks()])
      .then(([s, b]) => {
        setSources(s);
        setBenchmarks(b);
      })
      .catch(() => setOffline(true));
  }, []);

  const latestDone = benchmarks?.find(
    (b) => b.status === "succeeded" && b.summary?.comparison,
  );
  const cmp = latestDone?.summary?.comparison;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Command Center</h1>
        <p className="mt-1 text-sm text-ink-400">
          Adaptive inference runtime — minimum sufficient context per task,
          measured against a conventional RAG baseline.
        </p>
      </div>

      {offline && (
        <div className="panel border-signal-amber/40 p-4 text-sm text-signal-amber">
          Runtime not reachable. Start it with{" "}
          <code className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-xs">
            docker compose up
          </code>{" "}
          — or explore the replay demo pages.
        </div>
      )}

      {/* Headline comparison from the latest real benchmark */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="panel p-5">
          <div className="stat-label">Input-token reduction</div>
          <div className="stat-value mt-2 text-signal-green">
            {cmp ? `${cmp.input_token_reduction_pct}%` : "—"}
          </div>
          <div className="mt-1 text-[11px] text-ink-500">
            {latestDone ? `benchmark: ${latestDone.name}` : "no completed benchmark yet"}
          </div>
        </div>
        <div className="panel p-5">
          <div className="stat-label">Quality retention</div>
          <div className="stat-value mt-2 text-signal-blue">
            {cmp?.quality_retention_pct != null
              ? `${cmp.quality_retention_pct}%`
              : "—"}
          </div>
          <div className="mt-1 text-[11px] text-ink-500">
            keyword-grounded scoring vs baseline
          </div>
        </div>
        <div className="panel p-5">
          <div className="stat-label">Latency ratio</div>
          <div className="stat-value mt-2">
            {cmp?.latency_ratio != null ? `${cmp.latency_ratio}×` : "—"}
          </div>
          <div className="mt-1 text-[11px] text-ink-500">
            cortex / baseline wall time
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Knowledge sources */}
        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">Knowledge Sources</span>
            <Link href="/playground" className="text-[11px] text-signal-blue hover:underline">
              query →
            </Link>
          </div>
          <div className="divide-y divide-ink-800">
            {sources === null && !offline && (
              <div className="p-4 text-sm text-ink-500">loading…</div>
            )}
            {sources?.length === 0 && (
              <div className="p-4 text-sm text-ink-500">
                No sources ingested yet.
              </div>
            )}
            {sources?.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-4">
                <div>
                  <div className="text-sm font-medium">{s.display_name}</div>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-500">
                    {s.latest_version
                      ? `${s.latest_version.commit_sha.slice(0, 10)} · ${
                          s.latest_version.stats.artifacts ?? "?"
                        } artifacts · ${s.latest_version.stats.edges ?? "?"} edges`
                      : "no version"}
                  </div>
                </div>
                <span
                  className={`badge ${
                    s.latest_version?.status === "ready"
                      ? "bg-signal-green/10 text-signal-green"
                      : "bg-signal-amber/10 text-signal-amber"
                  }`}
                >
                  {s.latest_version?.status ?? "empty"}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Benchmarks */}
        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">Benchmark Runs</span>
            <Link href="/benchmarks" className="text-[11px] text-signal-blue hover:underline">
              all →
            </Link>
          </div>
          <div className="divide-y divide-ink-800">
            {benchmarks?.length === 0 && (
              <div className="p-4 text-sm text-ink-500">No benchmark runs yet.</div>
            )}
            {benchmarks?.slice(0, 5).map((b) => (
              <Link
                key={b.id}
                href={`/benchmarks/${b.id}`}
                className="flex items-center justify-between p-4 hover:bg-ink-850"
              >
                <div>
                  <div className="text-sm">{b.name}</div>
                  <div className="mt-0.5 font-mono text-[11px] text-ink-500">
                    {new Date(b.created_at).toLocaleString()}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {b.summary?.comparison && (
                    <span className="font-mono text-xs text-signal-green">
                      −{b.summary.comparison.input_token_reduction_pct}% tokens
                    </span>
                  )}
                  <span
                    className={`badge ${
                      b.status === "succeeded"
                        ? "bg-signal-green/10 text-signal-green"
                        : b.status === "running"
                          ? "bg-signal-blue/10 text-signal-blue"
                          : "bg-signal-red/10 text-signal-red"
                    }`}
                  >
                    {b.status}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>

      {/* Architecture strip */}
      <section className="panel p-5">
        <div className="panel-title mb-4">Runtime Pipeline</div>
        <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
          {[
            "Task Profiler",
            "Requirement Graph",
            "Hybrid Retrieval",
            "Context Compiler",
            "Semantic Virtual Memory",
            "Inference",
            "Sufficiency Evaluator",
          ].map((stage, i, arr) => (
            <span key={stage} className="flex items-center gap-2">
              <span className="rounded border border-ink-600 bg-ink-850 px-2.5 py-1.5 text-ink-200">
                {stage}
              </span>
              {i < arr.length - 1 && <span className="text-ink-500">→</span>}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
