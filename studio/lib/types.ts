// Typed contracts mirroring the CortexOS runtime API.

export type ExecutionMode = "cortex" | "baseline";

export type EventType =
  | "TASK_RECEIVED"
  | "TASK_PROFILED"
  | "REQUIREMENTS_CREATED"
  | "RETRIEVAL_STARTED"
  | "CANDIDATE_FOUND"
  | "CANDIDATE_REJECTED"
  | "CONTEXT_DEDUPLICATED"
  | "CONTEXT_COMPRESSED"
  | "CONTEXT_COMPILED"
  | "MODEL_SELECTED"
  | "INFERENCE_STARTED"
  | "INFERENCE_COMPLETED"
  | "PAGE_FAULT"
  | "PAGE_IN"
  | "PAGE_OUT"
  | "EVICT"
  | "PIN"
  | "INVALIDATE"
  | "SUFFICIENCY_CHECKED"
  | "ESCALATION_TRIGGERED"
  | "EXECUTION_COMPLETED"
  | "EXECUTION_FAILED"
  | "DONE";

export interface ExecutionEvent {
  seq: number;
  event_type: EventType;
  payload: Record<string, unknown>;
  ts: string;
}

export interface Execution {
  id: string;
  mode: ExecutionMode;
  query: string;
  answer: string | null;
  status: "running" | "succeeded" | "failed";
  failure_reason: string | null;
  metrics: ExecutionMetrics;
  source_version_id: string;
  session_id: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface BudgetDecision {
  operation: string;
  decision: "SKIP" | "EXECUTE" | "ESCALATE";
  reason: string;
}

export interface ExecutionMetrics {
  input_tokens?: number;
  output_tokens?: number;
  context_tokens_sent?: number;
  candidate_tokens?: number;
  context_reduction_pct?: number;
  artifacts_included?: number;
  artifacts_rejected?: number;
  retrieved_chunks?: number;
  rounds?: number;
  retrieval_ms?: number;
  inference_ms?: number;
  compile_ms?: number;
  requirements_ms?: number;
  total_ms?: number;
  // inference-budget instrumentation
  path?: "fast" | "deep";
  intent?: "explain" | "debug" | "generate";
  generation_calls?: number;
  embedding_calls?: number;
  decisions?: BudgetDecision[];
  svm?: {
    pages_reused: number;
    pages_faulted_in: number;
    resident_pages: number;
    resident_tokens: number;
  };
}

// --- knowledge graph / architecture (from /v1/sources/{version}/…) ---

export interface GraphNode {
  id: string;
  qualified_name: string;
  label: string;
  kind: string;
  path: string;
  language: string | null;
  tokens: number;
  degree: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  kind: string;
}

export interface RepoGraph {
  version_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
}

export interface ArchitectureFile {
  id: string;
  path: string;
  language: string | null;
  artifacts: number;
  tokens: number;
}

export interface ArchitectureEdge {
  from: string;
  to: string;
  kind: string;
  weight: number;
}

export interface Architecture {
  version_id: string;
  files: ArchitectureFile[];
  edges: ArchitectureEdge[];
}

export interface ArtifactDetail {
  id: string;
  qualified_name: string;
  kind: string;
  path: string;
  language: string | null;
  span_start_line: number;
  span_end_line: number;
  tokens: number;
  raw_text: string;
  summary_text: string | null;
  facts: unknown[] | null;
  github_url: string | null;
}

// --- Change Impact Guard ---

export interface ImpactArtifact {
  qualified_name: string;
  symbol: string;
  path: string;
  kind: string;
  edge_kind: string | null;
  hop: string;
}

export interface ImpactReport {
  risk_level: "HIGH" | "MEDIUM" | "LOW";
  risk_reasons: string[];
  confidence: number;
  sensitivity: string[];
  changed_files: string[];
  changed_artifacts: ImpactArtifact[];
  direct_impact: ImpactArtifact[];
  indirect_impact: ImpactArtifact[];
  problems: string[];
  recommended_tests: string[];
  suggested_patch: string;
  summary: string;
  narrative_raw: string;
  metrics: ExecutionMetrics & { model_calls?: number };
  evidence_grounded: boolean;
}

export interface Neighbors {
  depends_on: ImpactArtifact[];
  dependents: ImpactArtifact[];
}

export interface ArtifactRef {
  id: string;
  qualified_name: string;
  kind: string;
  path: string;
  language: string | null;
  span_start_line: number;
  span_end_line: number;
  github_url: string | null;
}

export interface SourceSummary {
  id: string;
  uri: string;
  display_name: string;
  latest_version: {
    id: string;
    commit_sha: string;
    status: string;
    stats: Record<string, number>;
    ingested_at: string | null;
  } | null;
}

export interface BenchmarkSummary {
  id: string;
  name: string;
  status: string;
  created_at: string;
  finished_at: string | null;
  summary: BenchmarkReportSummary | null;
}

export interface BenchmarkReportSummary {
  baseline?: ModeSummary;
  cortex?: ModeSummary;
  comparison?: {
    input_token_reduction_pct: number;
    quality_retention_pct: number | null;
    latency_ratio: number | null;
  };
}

export interface ModeSummary {
  completed: number;
  failed?: number;
  mean_input_tokens?: number;
  median_input_tokens?: number;
  mean_quality?: number;
  mean_total_ms?: number;
}

export interface BenchmarkRun {
  id: string;
  name: string;
  status: string;
  error: string | null;
  report: {
    summary: BenchmarkReportSummary;
    per_question: PerQuestionResult[];
    models: { task_model: string; embed_model: string };
    question_count: number;
    generated_at: string;
  } | null;
  created_at: string;
  finished_at: string | null;
}

export interface PerQuestionResult {
  id: string;
  category: string;
  baseline?: QuestionModeResult;
  cortex?: QuestionModeResult;
}

export interface QuestionModeResult {
  execution_id: string;
  answer?: string;
  error?: string;
  quality: number;
  input_tokens?: number;
  output_tokens?: number;
  total_ms?: number;
  rounds?: number;
}

export interface JobInfo {
  id: string;
  kind: string;
  status:
    | "queued"
    | "running"
    | "waiting_model"
    | "cancellation_requested"
    | "succeeded"
    | "failed"
    | "cancelled";
  stage: string | null;
  progress: { done: number; total: number | null } | null;
  attempts: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  uri: string | null;
}

export interface HealthStatus {
  status: "ok" | "degraded" | "unavailable";
  version?: string;
  checks: Record<string, string>;
}
