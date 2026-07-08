// Runtime API client. In demo mode (Vercel, no runtime connected) the
// pages fall back to recorded traces — see lib/eventStream.ts.

import type {
  BenchmarkRun,
  BenchmarkSummary,
  Execution,
  ExecutionEvent,
  HealthStatus,
  SourceSummary,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_CORTEX_API_URL ?? "http://localhost:8000";

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path}: HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  health: () => get<HealthStatus>("/health"),
  sources: () => get<SourceSummary[]>("/v1/sources"),
  ingestSource: (uri: string, displayName?: string) =>
    post<{ job_id: string }>("/v1/sources", { uri, display_name: displayName }),
  createExecution: (body: {
    query: string;
    mode: string;
    session_id?: string | null;
  }) => post<{ execution_id: string }>("/v1/executions", body),
  execution: (id: string) => get<Execution>(`/v1/executions/${id}`),
  executionEvents: (id: string) =>
    get<ExecutionEvent[]>(`/v1/executions/${id}/events`),
  benchmarks: () => get<BenchmarkSummary[]>("/v1/benchmarks"),
  benchmark: (id: string) => get<BenchmarkRun>(`/v1/benchmarks/${id}`),
  runBenchmark: (suite: string) =>
    post<{ benchmark_run_id: string }>("/v1/benchmarks", { suite }),
};
