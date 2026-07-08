"use client";

// Recent executions across playground and benchmarks.

import Link from "next/link";
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import type { Execution } from "@/lib/types";

export default function ExecutionsPage() {
  const [executions, setExecutions] = useState<Execution[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/v1/executions?limit=50`, { cache: "no-store" })
      .then((r) => r.json())
      .then(setExecutions)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Executions</h1>
        <p className="mt-1 text-sm text-ink-400">
          Every query run through the runtime, with its full decision trace.
        </p>
      </div>

      {error && <div className="panel p-4 text-sm text-signal-red">{error}</div>}

      <section className="panel overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-ink-700 text-[11px] uppercase tracking-wider text-ink-400">
              <th className="px-4 py-2.5">Query</th>
              <th className="px-4 py-2.5">Mode</th>
              <th className="px-4 py-2.5 text-right">Input tok</th>
              <th className="px-4 py-2.5 text-right">Reduction</th>
              <th className="px-4 py-2.5 text-right">Time</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-800 font-mono text-xs">
            {executions?.map((e) => (
              <tr key={e.id} className="hover:bg-ink-850">
                <td className="max-w-md px-4 py-2.5">
                  <Link
                    href={`/executions/${e.id}`}
                    className="block truncate text-ink-200 hover:text-signal-blue"
                  >
                    {e.query}
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={
                      e.mode === "cortex"
                        ? "text-signal-blue"
                        : "text-signal-amber"
                    }
                  >
                    {e.mode}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-right">
                  {e.metrics?.input_tokens?.toLocaleString() ?? "—"}
                </td>
                <td className="px-4 py-2.5 text-right text-signal-green">
                  {e.metrics?.context_reduction_pct != null
                    ? `−${e.metrics.context_reduction_pct}%`
                    : "—"}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {e.metrics?.total_ms != null
                    ? `${(e.metrics.total_ms / 1000).toFixed(1)}s`
                    : "—"}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`badge ${
                      e.status === "succeeded"
                        ? "bg-signal-green/10 text-signal-green"
                        : e.status === "running"
                          ? "bg-signal-blue/10 text-signal-blue"
                          : "bg-signal-red/10 text-signal-red"
                    }`}
                  >
                    {e.status}
                  </span>
                </td>
              </tr>
            ))}
            {executions?.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-ink-500">
                  No executions yet — try the playground.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
