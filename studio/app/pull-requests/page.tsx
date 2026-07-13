"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useRepo } from "@/lib/repo-context";
import type { ImpactReport as Report } from "@/lib/types";
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

const PHASES = [
  "Parsing the diff",
  "Resolving changed artifacts",
  "Tracing blast radius through the graph",
  "Compiling minimum evidence",
  "Assessing risk & writing review",
];

export default function ImpactGuardPage() {
  const { versionId, selected, isReady, loading } = useRepo();
  const [diff, setDiff] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<ArtifactTarget | null>(null);
  const phaseTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (phaseTimer.current) clearInterval(phaseTimer.current);
    };
  }, []);

  const analyze = async () => {
    if (!versionId || !diff.trim() || running) return;
    setRunning(true);
    setError(null);
    setReport(null);
    setPhase(0);
    // structural phases finish fast; the last (model) phase dominates — advance
    // through the early ones, then hold on the final phase until the response.
    phaseTimer.current = setInterval(
      () => setPhase((p) => Math.min(p + 1, PHASES.length - 1)),
      1400,
    );
    try {
      const r = await api.impact(versionId, diff);
      setReport(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (phaseTimer.current) clearInterval(phaseTimer.current);
      setRunning(false);
    }
  };

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

        <div className="panel p-3">
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
        </div>

        {error && (
          <div className="panel mt-4 border-signal-red/30 p-4 text-sm text-signal-red">
            {error}
          </div>
        )}

        {running && (
          <div className="panel mt-4 p-4">
            <ul className="space-y-2.5">
              {PHASES.map((label, i) => (
                <li key={label} className="flex items-center gap-3 text-sm">
                  <span className="flex h-5 w-5 items-center justify-center">
                    {i < phase ? (
                      <IconCheck className="text-signal-green" />
                    ) : i === phase ? (
                      <IconSpinner className="text-signal-blue" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-ink-700" />
                    )}
                  </span>
                  <span className={i <= phase ? "text-ink-200" : "text-ink-600"}>
                    {label}
                    {i === phase ? "…" : ""}
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
