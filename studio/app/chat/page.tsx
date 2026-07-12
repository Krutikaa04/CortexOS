"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { LiveExecutionEventStream } from "@/lib/eventStream";
import { useRepo } from "@/lib/repo-context";
import { filesUsed } from "@/lib/execution-insights";
import type { Execution, ExecutionEvent } from "@/lib/types";
import { AnswerBody } from "@/components/AnswerBody";
import { ArtifactDrawer, type ArtifactTarget } from "@/components/ArtifactDrawer";
import { FilesUsed } from "@/components/FilesUsed";
import { RuntimePanel } from "@/components/RuntimePanel";
import { StageIndicator } from "@/components/StageIndicator";
import { CopyButton } from "@/components/CodeBlock";
import { IconSend, IconSpinner } from "@/components/icons";

interface Turn {
  id: string;
  query: string;
  events: ExecutionEvent[];
  execution: Execution | null;
  status: "running" | "done" | "error";
  error?: string;
  baselineTokens: number | null;
  baselinePending: boolean;
}

const EXAMPLES = [
  "What does the Signer class do?",
  "Where is the signature validated?",
  "What breaks if the Serializer signature changes?",
  "Explain how signing and unsigning flow through the codebase.",
];

const BASELINE_POLL_MS = 4000;
const BASELINE_TIMEOUT_MS = 10 * 60_000;

export default function ChatPage() {
  const { versionId, selected, isReady, loading } = useRepo();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<ArtifactTarget | null>(null);

  const unsubRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const running = turns.some((t) => t.status === "running");
  const active = turns.find((t) => t.id === activeId) ?? null;
  const showPanel = active?.execution?.status === "succeeded" || active?.status === "running";

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  useEffect(() => () => unsubRef.current?.(), []);

  const patchTurn = useCallback((id: string, patch: Partial<Turn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const ask = useCallback(
    async (q: string) => {
      const text = q.trim();
      if (!text || running || !versionId) return;
      setQuery("");
      try {
        const { execution_id } = await api.createExecution({
          query: text,
          mode: "cortex",
          source_version_id: versionId,
        });
        const turn: Turn = {
          id: execution_id,
          query: text,
          events: [],
          execution: null,
          status: "running",
          baselineTokens: null,
          baselinePending: false,
        };
        setTurns((prev) => [...prev, turn]);
        setActiveId(execution_id);

        const stream = new LiveExecutionEventStream(execution_id);
        unsubRef.current = stream.subscribe(
          (event) =>
            setTurns((prev) =>
              prev.map((t) =>
                t.id === execution_id ? { ...t, events: [...t.events, event] } : t,
              ),
            ),
          async () => {
            try {
              const final = await api.execution(execution_id);
              patchTurn(execution_id, { execution: final, status: "done" });
            } catch (e) {
              patchTurn(execution_id, {
                status: "error",
                error: e instanceof Error ? e.message : String(e),
              });
            }
          },
          (err) => patchTurn(execution_id, { status: "error", error: err.message }),
        );
      } catch (e) {
        // surface create failure as a transient error turn
        const id = `err-${Date.now()}`;
        setTurns((prev) => [
          ...prev,
          {
            id,
            query: text,
            events: [],
            execution: null,
            status: "error",
            error: e instanceof Error ? e.message : String(e),
            baselineTokens: null,
            baselinePending: false,
          },
        ]);
      }
    },
    [running, versionId, patchTurn],
  );

  const runBaseline = useCallback(
    async (turn: Turn) => {
      if (!versionId || turn.baselinePending) return;
      patchTurn(turn.id, { baselinePending: true });
      try {
        const { execution_id } = await api.createExecution({
          query: turn.query,
          mode: "baseline",
          source_version_id: versionId,
        });
        const started = Date.now();
        const poll = setInterval(async () => {
          try {
            const b = await api.execution(execution_id);
            if (b.status === "succeeded") {
              clearInterval(poll);
              patchTurn(turn.id, {
                baselineTokens: b.metrics?.input_tokens ?? null,
                baselinePending: false,
              });
            } else if (b.status === "failed" || Date.now() - started > BASELINE_TIMEOUT_MS) {
              clearInterval(poll);
              patchTurn(turn.id, { baselinePending: false });
            }
          } catch {
            /* transient */
          }
        }, BASELINE_POLL_MS);
      } catch {
        patchTurn(turn.id, { baselinePending: false });
      }
    },
    [versionId, patchTurn],
  );

  const openFile = useCallback(
    (qualifiedName: string) => {
      if (versionId) setDrawer({ versionId, qualifiedName });
    },
    [versionId],
  );

  // ---- guards ----
  if (!loading && !selected) return <EmptyRepoState kind="none" />;
  if (!loading && selected && !isReady) return <EmptyRepoState kind="not-ready" name={selected.display_name} />;

  const empty = turns.length === 0;

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col">
        {/* conversation */}
        <div ref={scrollRef} className="flex-1 overflow-auto">
          <div className="mx-auto w-full max-w-3xl px-6 py-8">
            {empty ? (
              <WelcomeState onPick={(q) => ask(q)} disabled={!versionId} />
            ) : (
              <div className="space-y-8">
                {turns.map((turn) => (
                  <div key={turn.id} className="animate-fade-up space-y-4">
                    <div className="flex">
                      <div
                        className="bubble-user cursor-pointer"
                        onClick={() => setActiveId(turn.id)}
                      >
                        {turn.query}
                      </div>
                    </div>

                    {turn.status === "running" && <StageIndicator events={turn.events} />}

                    {turn.status === "error" && (
                      <div className="panel border-signal-red/30 p-4 text-sm text-signal-red">
                        {turn.error}
                      </div>
                    )}

                    {turn.execution && (
                      <AnswerTurn
                        turn={turn}
                        onOpenFile={openFile}
                        onFocus={() => setActiveId(turn.id)}
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* composer */}
        <Composer
          value={query}
          onChange={setQuery}
          onSend={() => ask(query)}
          disabled={!versionId}
          running={running}
          repoName={selected?.display_name}
        />
      </div>

      {/* right runtime panel */}
      {showPanel && active && (
        <div className="hidden w-[340px] shrink-0 border-l border-ink-800 bg-ink-950/40 lg:block">
          {active.execution ? (
            <RuntimePanel
              execution={active.execution}
              events={active.events}
              baselineTokens={active.baselineTokens}
              baselinePending={active.baselinePending}
              onRunBaseline={() => runBaseline(active)}
              onOpenFile={openFile}
            />
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-center text-xs text-ink-500">
              Runtime metrics appear here once the answer is ready.
            </div>
          )}
        </div>
      )}

      <ArtifactDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}

function AnswerTurn({
  turn,
  onOpenFile,
  onFocus,
}: {
  turn: Turn;
  onOpenFile: (qn: string) => void;
  onFocus: () => void;
}) {
  const exec = turn.execution!;
  const files = filesUsed(turn.events);
  const answer = exec.answer ?? exec.failure_reason ?? "No answer produced.";
  const intent = exec.metrics?.intent;
  const intentChip =
    intent === "debug"
      ? { label: "Bug fix", cls: "bg-signal-red/10 text-signal-red" }
      : intent === "generate"
        ? { label: "Code generation", cls: "bg-signal-cyan/10 text-signal-cyan" }
        : null;
  return (
    <div className="space-y-4" onMouseEnter={onFocus}>
      {intentChip && (
        <span className={`badge ${intentChip.cls}`}>{intentChip.label}</span>
      )}
      <div className="group relative">
        <AnswerBody text={answer} />
        <div className="absolute -right-1 -top-1 opacity-0 transition-opacity group-hover:opacity-100">
          <CopyButton text={answer} label="Copy answer" />
        </div>
      </div>

      {files.length > 0 && (
        <div className="panel p-3">
          <div className="mb-2 px-1 text-[10px] uppercase tracking-wider text-ink-500">
            Relevant files &amp; functions
          </div>
          <FilesUsed files={files} onOpen={onOpenFile} />
        </div>
      )}
    </div>
  );
}

function Composer({
  value,
  onChange,
  onSend,
  disabled,
  running,
  repoName,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
  running: boolean;
  repoName?: string;
}) {
  return (
    <div className="border-t border-ink-800 bg-ink-950/70 px-6 py-4">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-ink-700 bg-ink-900 p-2 transition-colors focus-within:border-signal-blue/60">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            rows={1}
            placeholder={
              disabled
                ? "Select a ready repository to start…"
                : "Ask about the repository, request code, or describe a bug to fix…"
            }
            disabled={disabled}
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] text-ink-100 outline-none placeholder:text-ink-500 disabled:opacity-50"
          />
          <button
            onClick={onSend}
            disabled={disabled || running || !value.trim()}
            className="btn-primary h-9 w-9 shrink-0 !p-0"
            title="Send"
          >
            {running ? <IconSpinner /> : <IconSend />}
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-ink-600">
          <span>
            {repoName ? (
              <>
                Answering over <span className="text-ink-400">{repoName}</span> · live execution
              </>
            ) : (
              "No repository selected"
            )}
          </span>
          <span>
            <span className="kbd">Enter</span> to send · <span className="kbd">Shift</span>+
            <span className="kbd">Enter</span> for newline
          </span>
        </div>
      </div>
    </div>
  );
}

function WelcomeState({ onPick, disabled }: { onPick: (q: string) => void; disabled: boolean }) {
  return (
    <div className="flex flex-col items-center pt-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-signal-blue/15 font-mono text-lg font-bold text-signal-blue">
        C
      </div>
      <h1 className="mt-4 text-2xl font-semibold text-ink-100">
        Ask your repository anything
      </h1>
      <p className="mt-2 max-w-md text-sm text-ink-400">
        Understand code, trace impact, generate changes, or debug — answered by
        live execution over the real repository at minimum inference cost.
      </p>
      <div className="mt-8 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            disabled={disabled}
            onClick={() => onPick(ex)}
            className="rounded-xl border border-ink-800 bg-ink-900/50 px-4 py-3 text-left text-[13px] text-ink-300 transition-colors hover:border-ink-600 hover:text-ink-100 disabled:opacity-40"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}

function EmptyRepoState({
  kind,
  name,
}: {
  kind: "none" | "not-ready";
  name?: string;
}) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="max-w-sm text-center">
        <h1 className="text-lg font-semibold text-ink-100">
          {kind === "none" ? "No repository yet" : `${name} is still ingesting`}
        </h1>
        <p className="mt-2 text-sm text-ink-400">
          {kind === "none"
            ? "Add a Git repository to start asking questions about real code."
            : "Once ingestion finishes, this repository will be ready to query."}
        </p>
        <Link href="/repositories" className="btn-primary mt-5 inline-flex">
          Go to Repositories
        </Link>
      </div>
    </div>
  );
}
