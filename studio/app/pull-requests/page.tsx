"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { LiveExecutionEventStream } from "@/lib/eventStream";
import { useRepo } from "@/lib/repo-context";
import type { ExecutionEvent, ImpactReport as Report } from "@/lib/types";
import { ImpactReport } from "@/components/ImpactReport";
import { ArtifactDrawer, type ArtifactTarget } from "@/components/ArtifactDrawer";
import { IconCheck, IconSpinner } from "@/components/icons";

const EXAMPLE_DIFF = `diff --git a/src/itsdangerous/signer.py b/src/itsdangerous/signer.py
--- a/src/itsdangerous/signer.py
+++ b/src/itsdangerous/signer.py
@@ -244,7 +244,9 @@ class Signer:
     def unsign(self, signed_value):
-        signed_value = want_bytes(signed_value)
+        if signed_value is None:
+            return b""
+        signed_value = want_bytes(signed_value)
         if self.sep not in signed_value:
             raise BadSignature("no sep")
`;

// Each phase is marked done when its event arrives on the live feed — real
// progress, not a timer. The final phase spans the one narrative model call.
const PHASES: { label: string; doneOn: string }[] = [
  { label: "Parsing the diff", doneOn: "IMPACT_DIFF_PARSED" },
  { label: "Resolving changed artifacts", doneOn: "IMPACT_ARTIFACTS_RESOLVED" },
  { label: "Tracing blast radius through the graph", doneOn: "IMPACT_BLAST_RADIUS" },
  { label: "Compiling minimum evidence", doneOn: "IMPACT_EVIDENCE_COMPILED" },
  { label: "Assessing risk & writing review", doneOn: "IMPACT_COMPLETED" },
];

type Mode = "diff" | "github";

export default function ImpactGuardPage() {
  const { versionId, selected, isReady, loading } = useRepo();
  const [mode, setMode] = useState<Mode>("diff");
  const [diff, setDiff] = useState("");
  const [prUrl, setPrUrl] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<ArtifactTarget | null>(null);
  const unsubRef = useRef<(() => void) | null>(null);

  useEffect(() => () => unsubRef.current?.(), []);

  // Both input modes feed the same background analysis + live event stream.
  const track = (execution_id: string) => {
    const stream = new LiveExecutionEventStream(execution_id);
    unsubRef.current = stream.subscribe(
      (event) => setEvents((prev) => [...prev, event]),
      async (status) => {
        if (status === "failed") {
          const ex = await api.execution(execution_id).catch(() => null);
          setError(ex?.failure_reason ?? "impact analysis failed");
        } else {
          const ex = await api.execution(execution_id);
          setReport(ex.metrics as unknown as Report);
        }
        setRunning(false);
      },
      (err) => {
        setError(err.message);
        setRunning(false);
      },
    );
  };

  const analyze = async () => {
    const ready = mode === "diff" ? diff.trim() : prUrl.trim();
    if (!versionId || !ready || running) return;
    setRunning(true);
    setError(null);
    setReport(null);
    setEvents([]);
    unsubRef.current?.();
    try {
      const { execution_id } =
        mode === "diff"
          ? await api.startImpact(versionId, diff)
          : await api.startGithubImpact(versionId, prUrl);
      track(execution_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRunning(false);
    }
  };

  const doneCount = PHASES.filter((p) =>
    events.some((e) => e.event_type === p.doneOn),
  ).length;

  if (!loading && (!selected || !isReady))
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="max-w-sm text-center">
          <h1 className="text-lg font-semibold text-ink-100">Change Impact Guard</h1>
          <p className="mt-2 text-sm text-ink-400">
            Select a ready repository to analyze a change against its dependency graph.
          </p>
          <Link href="/repositories" className="btn-primary mt-5 inline-flex">
            Go to Repositories
          </Link>
        </div>
      </div>
    );

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto max-w-5xl px-8 py-8">
        <header className="mb-5">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-ink-100">Change Impact Guard</h1>
            <span className="badge bg-signal-blue/10 text-signal-blue">flagship</span>
          </div>
          <p className="mt-1 text-sm text-ink-400">
            Paste a diff. CortexOS traces its blast radius through the real
            dependency graph of {selected?.display_name} and returns a grounded
            risk review — every claim backed by repository evidence.
          </p>
        </header>

        <div className="mb-3 flex gap-1 rounded-lg border border-ink-800 bg-ink-900/50 p-1 text-xs w-fit">
          {(["diff", "github"] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              disabled={running}
              className={`rounded-md px-3 py-1.5 transition-colors ${
                mode === m
                  ? "bg-ink-800 text-ink-100"
                  : "text-ink-400 hover:text-ink-200"
              }`}
            >
              {m === "diff" ? "Paste diff" : "GitHub PR"}
            </button>
          ))}
        </div>

        <div className="panel p-3">
          {mode === "diff" ? (
            <>
              <textarea
                value={diff}
                onChange={(e) => setDiff(e.target.value)}
                placeholder="Paste a unified diff (git diff / PR patch)…"
                className="h-44 w-full resize-y rounded-lg bg-transparent px-3 py-2 font-mono text-[12.5px] text-ink-100 outline-none placeholder:text-ink-600"
              />
              <div className="flex items-center justify-between border-t border-ink-800 px-1 pt-3">
                <button
                  onClick={() => setDiff(EXAMPLE_DIFF)}
                  className="text-xs text-ink-400 hover:text-signal-blue"
                >
                  Load example diff
                </button>
                <button
                  onClick={analyze}
                  disabled={running || !diff.trim()}
                  className="btn-primary"
                >
                  {running ? <IconSpinner /> : null}
                  {running ? "Analyzing…" : "Analyze impact"}
                </button>
              </div>
            </>
          ) : (
            <>
              <input
                value={prUrl}
                onChange={(e) => setPrUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && analyze()}
                placeholder="https://github.com/owner/repo/pull/123"
                className="w-full rounded-lg bg-transparent px-3 py-2 font-mono text-[12.5px] text-ink-100 outline-none placeholder:text-ink-600"
              />
              <div className="flex items-center justify-between border-t border-ink-800 px-1 pt-3">
                <span className="text-xs text-ink-500">
                  Fetches the PR&apos;s diff from GitHub — public repositories only.
                </span>
                <button
                  onClick={analyze}
                  disabled={running || !prUrl.trim()}
                  className="btn-primary"
                >
                  {running ? <IconSpinner /> : null}
                  {running ? "Analyzing…" : "Analyze PR"}
                </button>
              </div>
            </>
          )}
        </div>

        {error && (
          <div className="panel mt-4 border-signal-red/30 p-4 text-sm text-signal-red">
            {error}
          </div>
        )}

        {running && (
          <div className="panel mt-4 p-4">
            <ul className="space-y-2.5">
              {PHASES.map((phase, i) => (
                <li key={phase.label} className="flex items-center gap-3 text-sm">
                  <span className="flex h-5 w-5 items-center justify-center">
                    {i < doneCount ? (
                      <IconCheck className="text-signal-green" />
                    ) : i === doneCount ? (
                      <IconSpinner className="text-signal-blue" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-ink-700" />
                    )}
                  </span>
                  <span className={i <= doneCount ? "text-ink-200" : "text-ink-600"}>
                    {phase.label}
                    {i === doneCount ? "…" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {report && (
          <div className="mt-6">
            <ImpactReport
              report={report}
              onOpenFile={(qn) => versionId && setDrawer({ versionId, qualifiedName: qn })}
            />
          </div>
        )}
      </div>
      <ArtifactDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
