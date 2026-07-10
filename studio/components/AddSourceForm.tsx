"use client";

// Add a repository to the knowledge layer, then track the REAL job:
// submission only proves a job was queued, so the form preserves the
// returned job ID and polls the backend for actual state — queued,
// cloning, parsing, linking, embedding (with honest done/total when the
// backend knows it), through ready / failed / cancelled. A cancel control
// is shown while cancellation is valid.

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { JobInfo } from "@/lib/types";

const POLL_MS = 3_000;

const TERMINAL: JobInfo["status"][] = ["succeeded", "failed", "cancelled"];

export function AddSourceForm({ onQueued }: { onQueued: () => void }) {
  const [uri, setUri] = useState("");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<JobInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const track = useCallback(
    (jobId: string) => {
      stopPolling();
      timerRef.current = setInterval(async () => {
        try {
          const j = await api.job(jobId);
          setJob(j);
          if (TERMINAL.includes(j.status)) {
            stopPolling();
            onQueued(); // final source refresh so READY/FAILED shows below
          }
        } catch {
          /* transient polling failure — keep trying until terminal */
        }
      }, POLL_MS);
    },
    [onQueued, stopPolling],
  );

  const submit = async () => {
    const trimmed = uri.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const { job_id } = await api.ingestSource(trimmed);
      setJob({
        id: job_id,
        kind: "ingest_source",
        status: "queued",
        stage: null,
        progress: null,
        attempts: 0,
        error: null,
        created_at: new Date().toISOString(),
        started_at: null,
        finished_at: null,
        uri: trimmed,
      });
      setUri("");
      onQueued();
      track(job_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!job) return;
    try {
      setJob(await api.cancelJob(job.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const cancellable =
    job != null &&
    ["queued", "running", "waiting_model"].includes(job.status);

  return (
    <div className="border-b border-ink-800 p-4">
      <div className="flex gap-2">
        <input
          value={uri}
          onChange={(e) => setUri(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="https://github.com/owner/repo — or a path mounted into the runtime"
          className="flex-1 rounded border border-ink-600 bg-ink-850 px-3 py-2 text-sm outline-none placeholder:text-ink-500 focus:border-signal-blue"
        />
        <button
          onClick={submit}
          disabled={busy || !uri.trim()}
          className="rounded bg-signal-blue px-4 py-2 text-sm font-semibold text-ink-950 transition-opacity disabled:opacity-40"
        >
          {busy ? "Queuing…" : "Add repository"}
        </button>
      </div>

      {job && (
        <div className="mt-3 flex items-center justify-between rounded border border-ink-700 bg-ink-850 px-3 py-2">
          <div className="flex items-center gap-3 font-mono text-xs">
            <StatusBadge job={job} />
            <span className="max-w-xs truncate text-ink-400">{job.uri}</span>
            {job.status === "failed" && job.error && (
              <span className="max-w-sm truncate text-signal-red" title={job.error}>
                {job.error}
              </span>
            )}
          </div>
          {cancellable && (
            <button
              onClick={cancel}
              className="rounded border border-signal-red/40 px-2.5 py-1 text-[11px] text-signal-red transition-colors hover:bg-signal-red/10"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      <p className="mt-2 text-[11px] leading-relaxed text-ink-500">
        Any public Git URL works. For a local folder: make it a Git repo
        (<code className="rounded bg-ink-800 px-1">git init && git add -A && git commit</code>),
        mount its parent directory into the containers in{" "}
        <code className="rounded bg-ink-800 px-1">docker-compose.dev.yml</code>, and paste
        the container-side path (e.g.{" "}
        <code className="rounded bg-ink-800 px-1">/data/local/my-project</code>).
      </p>
      {error && <p className="mt-2 text-xs text-signal-red">{error}</p>}
    </div>
  );
}

// Only real backend state is shown: the stage comes from worker checkpoints,
// and a count appears only when the backend honestly knows done/total.
function StatusBadge({ job }: { job: JobInfo }) {
  const label = describe(job);
  const tone =
    job.status === "succeeded"
      ? "bg-signal-green/10 text-signal-green"
      : job.status === "failed"
        ? "bg-signal-red/10 text-signal-red"
        : job.status === "cancelled" || job.status === "cancellation_requested"
          ? "bg-signal-amber/10 text-signal-amber"
          : "bg-signal-blue/10 text-signal-blue";
  const live = !TERMINAL.includes(job.status);
  return (
    <span className={`badge ${tone}`}>
      {live && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {label}
    </span>
  );
}

function describe(job: JobInfo): string {
  switch (job.status) {
    case "queued":
      return "QUEUED";
    case "cancellation_requested":
      return "CANCELLATION REQUESTED";
    case "cancelled":
      return "CANCELLED";
    case "succeeded":
      return "READY";
    case "failed":
      return "FAILED";
    case "waiting_model":
      return "WAITING FOR MODEL";
    case "running": {
      if (!job.stage) return "RUNNING";
      const name = job.stage.replace(/_/g, " ").toUpperCase();
      if (job.progress && job.progress.total != null) {
        return `${name} ${job.progress.done} / ${job.progress.total}`;
      }
      return name;
    }
  }
}
