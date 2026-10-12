// Runtime API client. Every call targets a live CortexOS runtime; there is
// no offline/demo fallback — all data comes from real executions.

import type {
  Architecture,
  ArtifactDetail,
  ArtifactRef,
  BenchmarkRun,
  BenchmarkSummary,
  ChatMessage,
  ChatSession,
  CycleItem,
  DeadCodeItem,
  Execution,
  FlowReport,
  InsightsOverview,
  ExecutionEvent,
  GraphStats,
  HealthStatus,
  ImpactHistoryEntry,
  JobInfo,
  Neighbors,
  RepoGraph,
  SourceSummary,
} from "./types";

// Runtime base URL is fully configuration-driven. In production (Vercel) set
// NEXT_PUBLIC_CORTEX_API_URL to the deployed backend; the localhost value is
// only a local-development fallback. Trailing slashes are trimmed so path
// concatenation is always correct.
export const API_URL = (
  process.env.NEXT_PUBLIC_CORTEX_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

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

async function send<T>(method: "PATCH" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path}: HTTP ${res.status}`);
  }
  return res.status === 204 ? (undefined as T) : res.json();
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
  graphStats: (versionId: string) =>
    get<GraphStats>(`/v1/sources/${versionId}/graph/stats`),
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

  // Change Impact Guard — kicks off a background analysis (mode='impact')
  // whose phases stream over the execution event feed; the finished report is
  // read back from the execution's metrics.
  startImpact: (versionId: string, diff: string) =>
    post<{ execution_id: string }>(`/v1/sources/${versionId}/impact`, { diff }),
  // Fetch a public GitHub PR's diff server-side and run the same analysis.
  startGithubImpact: (versionId: string, prUrl: string) =>
    post<{ execution_id: string }>(`/v1/sources/${versionId}/impact/github`, {
      pr_url: prUrl,
    }),
  // Persisted PR/impact analyses for a repository version (reuses executions).
  impactHistory: (versionId: string, limit = 20) =>
    get<ImpactHistoryEntry[]>(
      `/v1/sources/${versionId}/impact/history?limit=${limit}`,
    ),

  // --- Chat sessions (repository-scoped conversations) ---
  listSessions: (versionId: string) =>
    get<ChatSession[]>(`/v1/sessions?source_version_id=${versionId}`),
  createSession: (versionId: string, title?: string) =>
    post<ChatSession>("/v1/sessions", { source_version_id: versionId, title }),
  sessionMessages: (sessionId: string) =>
    get<ChatMessage[]>(`/v1/sessions/${sessionId}/messages`),
  renameSession: (sessionId: string, title: string) =>
    send<{ id: string; title: string }>("PATCH", `/v1/sessions/${sessionId}`, { title }),
  deleteSession: (sessionId: string) =>
    send<void>("DELETE", `/v1/sessions/${sessionId}`),

  // --- Engineering intelligence (deterministic graph analyses) ---
  deadCode: (versionId: string) =>
    get<{ count: number; items: DeadCodeItem[] }>(`/v1/sources/${versionId}/insights/dead-code`),
  cycles: (versionId: string) =>
    get<{ count: number; cycles: CycleItem[] }>(`/v1/sources/${versionId}/insights/cycles`),
  insightsOverview: (versionId: string) =>
    get<InsightsOverview>(`/v1/sources/${versionId}/insights/overview`),
  flow: (versionId: string, qualifiedName: string) =>
    get<FlowReport>(
      `/v1/sources/${versionId}/insights/flow?qualified_name=${encodeURIComponent(qualifiedName)}`,
    ),
};
