// Runtime API client. Every call targets a live CortexOS runtime; there is
// no offline/demo fallback — all data comes from real executions.

import type {
  Architecture,
  ArtifactDetail,
  ArtifactRef,
  BenchmarkRun,
  BenchmarkSummary,
  Execution,
  ExecutionEvent,
  HealthStatus,
  ImpactReport,
  JobInfo,
  Neighbors,
  RepoGraph,
  SourceSummary,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_CORTEX_API_URL ?? "http://localhost:8000";

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
  job: (id: string) => get<JobInfo>(`/v1/jobs/${id}`),
  cancelJob: (id: string) => post<JobInfo>(`/v1/jobs/${id}/cancel`, {}),
  createExecution: (body: {
    query: string;
    mode: string;
    source_version_id?: string | null;
    session_id?: string | null;
  }) => post<{ execution_id: string }>("/v1/executions", body),
  execution: (id: string) => get<Execution>(`/v1/executions/${id}`),
  executionEvents: (id: string) =>
    get<ExecutionEvent[]>(`/v1/executions/${id}/events`),
  benchmarks: () => get<BenchmarkSummary[]>("/v1/benchmarks"),
  benchmark: (id: string) => get<BenchmarkRun>(`/v1/benchmarks/${id}`),
  runBenchmark: (suite: string) =>
    post<{ benchmark_run_id: string }>("/v1/benchmarks", { suite }),

  // knowledge graph / architecture / source code (real ingested data)
  graph: (versionId: string, limit = 160, kinds?: string) =>
    get<RepoGraph>(
      `/v1/sources/${versionId}/graph?limit=${limit}` +
        (kinds ? `&kinds=${encodeURIComponent(kinds)}` : ""),
    ),
  architecture: (versionId: string) =>
    get<Architecture>(`/v1/sources/${versionId}/architecture`),
  artifact: (versionId: string, artifactId: string) =>
    get<ArtifactDetail>(`/v1/sources/${versionId}/artifacts/${artifactId}`),
  lookup: (versionId: string, qualifiedName: string) =>
    get<ArtifactRef>(
      `/v1/sources/${versionId}/lookup?qualified_name=${encodeURIComponent(qualifiedName)}`,
    ),
  neighbors: (versionId: string, artifactId: string) =>
    get<Neighbors>(`/v1/sources/${versionId}/artifacts/${artifactId}/neighbors`),

  // Change Impact Guard — analyze a diff against the repository graph.
  impact: (versionId: string, diff: string) =>
    post<ImpactReport>(`/v1/sources/${versionId}/impact`, { diff }),
};
