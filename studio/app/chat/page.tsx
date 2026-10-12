"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { LiveExecutionEventStream } from "@/lib/eventStream";
import { useRepo } from "@/lib/repo-context";
import { filesUsed } from "@/lib/execution-insights";
import type {
  ChatMessage,
  ChatSession,
  Execution,
  ExecutionEvent,
  GraphRagMetrics,
} from "@/lib/types";
import { AnswerBody } from "@/components/AnswerBody";
import { ArtifactDrawer, type ArtifactTarget } from "@/components/ArtifactDrawer";
import { FilesUsed } from "@/components/FilesUsed";
import { RuntimePanel } from "@/components/RuntimePanel";
import { KnowledgeGraphPanel } from "@/components/KnowledgeGraphPanel";
import { StageIndicator } from "@/components/StageIndicator";
import { CopyButton } from "@/components/CodeBlock";
import { IconClose, IconSend, IconSpinner } from "@/components/icons";

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

// Reconstruct a rendered Turn from a persisted message. Synthesizing a
// CONTEXT_COMPILED event lets the existing filesUsed()/AnswerTurn render the
// evidence panel for reloaded conversations, identical to a live turn.
function messageToTurn(m: ChatMessage): Turn {
  const events: ExecutionEvent[] = m.files.length
    ? [{
        seq: 0,
        event_type: "CONTEXT_COMPILED",
        ts: m.started_at,
        payload: {
          included: m.files.map((f) => ({
            qualified_name: f.qualified_name,
            representation: f.representation,
            tokens: f.tokens,
          })),
        },
      }]
    : [];
  const execution = {
    id: m.id,
    mode: "cortex",
    query: m.query,
    answer: m.answer,
    status: m.status,
    failure_reason: m.failure_reason,
    metrics: m.metrics ?? undefined,
    session_id: null,
    started_at: m.started_at,
    finished_at: m.started_at,
  } as unknown as Execution;
  return {
    id: m.id,
    query: m.query,
    events,
    execution,
    status: m.status === "failed" ? "error" : "done",
    error: m.failure_reason ?? undefined,
    baselineTokens: null,
    baselinePending: false,
  };
}

export default function ChatPage() {
  const { versionId, selected, isReady, loading } = useRepo();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [query, setQuery] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<ArtifactTarget | null>(null);

  const unsubRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const loadedVersionRef = useRef<string | null>(null);

  const running = turns.some((t) => t.status === "running");
  const active = turns.find((t) => t.id === activeId) ?? null;
  const showPanel = active?.execution?.status === "succeeded" || active?.status === "running";
  const empty = turns.length === 0;

  const refreshSessions = useCallback(async (vid: string) => {
    try {
      return await api.listSessions(vid);
    } catch {
      return [];
    }
  }, []);

  const loadMessages = useCallback(async (sid: string) => {
    setHistoryLoading(true);
    try {
      const msgs = await api.sessionMessages(sid);
      setTurns(msgs.map(messageToTurn));
      setActiveId(msgs.length ? msgs[msgs.length - 1].id : null);
    } catch {
      setTurns([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  // On repo change: load its conversations, open the most recent (or none).
  useEffect(() => {
    if (!versionId || loadedVersionRef.current === versionId) return;
    loadedVersionRef.current = versionId;
    setSessionsLoading(true);
    unsubRef.current?.();
    (async () => {
      const list = await refreshSessions(versionId);
      setSessions(list);
      if (list.length) {
        setSessionId(list[0].id);
        await loadMessages(list[0].id);
      } else {
        setSessionId(null);
        setTurns([]);
        setActiveId(null);
      }
      setSessionsLoading(false);
    })();
  }, [versionId, refreshSessions, loadMessages]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  useEffect(() => () => unsubRef.current?.(), []);

  const patchTurn = useCallback((id: string, patch: Partial<Turn>) => {
    setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const switchSession = useCallback(
    async (sid: string) => {
      if (sid === sessionId || running) return;
      unsubRef.current?.();
      setSessionId(sid);
      await loadMessages(sid);
    },
    [sessionId, running, loadMessages],
  );

  const newChat = useCallback(async () => {
    if (!versionId || running) return;
    unsubRef.current?.();
    try {
      const s = await api.createSession(versionId);
      setSessions((prev) => [s, ...prev]);
      setSessionId(s.id);
      setTurns([]);
      setActiveId(null);
    } catch {
      /* leave current state on failure */
    }
  }, [versionId, running]);

  const renameSession = useCallback(async (sid: string, title: string) => {
    const clean = title.trim();
    if (!clean) return;
    setSessions((prev) => prev.map((s) => (s.id === sid ? { ...s, title: clean } : s)));
    try {
      await api.renameSession(sid, clean);
    } catch {
      /* optimistic; ignore */
    }
  }, []);

  const deleteSession = useCallback(
    async (sid: string) => {
      const remaining = sessions.filter((s) => s.id !== sid);
      setSessions(remaining);
      try {
        await api.deleteSession(sid);
      } catch {
        /* ignore */
      }
      if (sid === sessionId) {
        if (remaining.length) {
          setSessionId(remaining[0].id);
          await loadMessages(remaining[0].id);
        } else {
          setSessionId(null);
          setTurns([]);
          setActiveId(null);
        }
      }
    },
    [sessions, sessionId, loadMessages],
  );

  const ask = useCallback(
    async (q: string) => {
      const text = q.trim();
      if (!text || running || !versionId) return;
      setQuery("");

      // Ensure a conversation exists (auto-create on first message).
      let sid = sessionId;
      let created: ChatSession | null = null;
      if (!sid) {
        try {
          created = await api.createSession(versionId);
          sid = created.id;
          setSessionId(sid);
          setSessions((prev) => [created!, ...prev]);
        } catch (e) {
          const id = `err-${Date.now()}`;
          setTurns((prev) => [
            ...prev,
            { id, query: text, events: [], execution: null, status: "error",
              error: e instanceof Error ? e.message : String(e),
              baselineTokens: null, baselinePending: false },
          ]);
          return;
        }
      }
      const isFirstMessage = turns.length === 0;

      try {
        const { execution_id } = await api.createExecution({
          query: text,
          mode: "cortex",
          source_version_id: versionId,
          session_id: sid,
        });
        const turn: Turn = {
          id: execution_id, query: text, events: [], execution: null,
          status: "running", baselineTokens: null, baselinePending: false,
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
              // Auto-title a brand-new conversation from its first question.
              if (isFirstMessage && sid) {
                const title = text.length > 48 ? `${text.slice(0, 48)}…` : text;
                renameSession(sid, title);
              }
              if (versionId) setSessions(await refreshSessions(versionId));
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
        const id = `err-${Date.now()}`;
        setTurns((prev) => [
          ...prev,
          { id, query: text, events: [], execution: null, status: "error",
            error: e instanceof Error ? e.message : String(e),
            baselineTokens: null, baselinePending: false },
        ]);
      }
    },
    [running, versionId, sessionId, turns.length, patchTurn, renameSession, refreshSessions],
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
  if (!loading && selected && !isReady)
    return <EmptyRepoState kind="not-ready" name={selected.display_name} />;

  return (
    <div className="flex h-full">
      <ChatSessionsSidebar
        sessions={sessions}
        activeId={sessionId}
        loading={sessionsLoading}
        disabled={running}
        onNew={newChat}
        onSwitch={switchSession}
        onRename={renameSession}
        onDelete={deleteSession}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 overflow-auto">
          <div className="mx-auto w-full max-w-3xl px-6 py-8">
            {historyLoading ? (
              <div className="flex items-center justify-center pt-16 text-sm text-ink-500">
                <IconSpinner /> <span className="ml-2">Loading conversation…</span>
              </div>
            ) : empty ? (
              <WelcomeState
                onPick={(q) => ask(q)}
                disabled={!versionId}
                versionId={versionId}
                onOpenArtifact={(artifactId) =>
                  versionId && setDrawer({ versionId, artifactId })
                }
              />
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
                        versionId={versionId}
                        onOpenArtifact={(artifactId) =>
                          versionId && setDrawer({ versionId, artifactId })
                        }
                      />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <Composer
          value={query}
          onChange={setQuery}
          onSend={() => ask(query)}
          disabled={!versionId}
          running={running}
          repoName={selected?.display_name}
        />
      </div>

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

function ChatSessionsSidebar({
  sessions,
  activeId,
  loading,
  disabled,
  onNew,
  onSwitch,
  onRename,
  onDelete,
}: {
  sessions: ChatSession[];
  activeId: string | null;
  loading: boolean;
  disabled: boolean;
  onNew: () => void;
  onSwitch: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startRename = (s: ChatSession) => {
    setEditingId(s.id);
    setDraft(s.title);
  };
  const commitRename = () => {
    if (editingId) onRename(editingId, draft);
    setEditingId(null);
  };

  return (
    <div className="hidden w-60 shrink-0 flex-col border-r border-ink-800 bg-ink-950/40 md:flex">
      <div className="p-3">
        <button
          onClick={onNew}
          disabled={disabled}
          className="btn-primary w-full justify-center disabled:opacity-40"
        >
          + New chat
        </button>
      </div>
      <div className="flex-1 overflow-auto px-2 pb-3">
        {loading ? (
          <div className="px-2 py-4 text-xs text-ink-500">Loading conversations…</div>
        ) : sessions.length === 0 ? (
          <div className="px-2 py-4 text-xs text-ink-600">
            No conversations yet. Start one to see it here.
          </div>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((s) => {
              const isActive = s.id === activeId;
              return (
                <div
                  key={s.id}
                  className={`group flex items-center gap-1 rounded-lg px-2 py-2 text-sm transition-colors ${
                    isActive ? "bg-ink-800 text-ink-100" : "text-ink-300 hover:bg-ink-900"
                  }`}
                >
                  {editingId === s.id ? (
                    <input
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename();
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="min-w-0 flex-1 rounded bg-ink-950 px-1.5 py-0.5 text-[13px] text-ink-100 outline-none"
                    />
                  ) : (
                    <button
                      onClick={() => onSwitch(s.id)}
                      className="min-w-0 flex-1 truncate text-left"
                      title={s.title}
                    >
                      {s.title}
                      <span className="ml-1 text-[10px] text-ink-600">
                        {s.message_count > 0 ? `· ${s.message_count}` : ""}
                      </span>
                    </button>
                  )}
                  {editingId !== s.id && (
                    <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        onClick={() => startRename(s)}
                        title="Rename"
                        className="rounded p-1 text-ink-500 hover:text-ink-200"
                      >
                        <svg viewBox="0 0 24 24" width="13" height="13" fill="none"
                          stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                          strokeLinejoin="round">
                          <path d="M12 20h9" />
                          <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => {
                          if (confirm(`Delete "${s.title}"? This removes its messages.`))
                            onDelete(s.id);
                        }}
                        title="Delete"
                        className="rounded p-1 text-ink-500 hover:text-signal-red"
                      >
                        <IconClose className="h-3 w-3" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function AnswerTurn({
  turn,
  onOpenFile,
  onFocus,
  versionId,
  onOpenArtifact,
}: {
  turn: Turn;
  onOpenFile: (qn: string) => void;
  onFocus: () => void;
  versionId: string | null;
  onOpenArtifact: (artifactId: string) => void;
}) {
  const gr = turn.execution?.metrics?.graph_rag;
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
      {intentChip && <span className={`badge ${intentChip.cls}`}>{intentChip.label}</span>}
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

      {gr && versionId && (
        <GraphReasoning gr={gr} versionId={versionId} onOpenArtifact={onOpenArtifact} />
      )}
    </div>
  );
}

// "Graph reasoning": the dependency path CortexOS traversed for this answer.
function GraphReasoning({
  gr,
  versionId,
  onOpenArtifact,
}: {
  gr: GraphRagMetrics;
  versionId: string;
  onOpenArtifact: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const names = new Map(gr.path.nodes.map((n) => [n.id, n.name]));
  // one readable line per edge: A -CALLS-> B
  const lines = gr.path.edges.slice(0, 8).map(
    (e) => `${names.get(e.from) ?? "?"} —${e.type}→ ${names.get(e.to) ?? "?"}`,
  );
  if (gr.engine !== "graph-rag")
    return (
      <div className="text-[11px] text-ink-500">
        Graph-RAG inactive for this answer
        {gr.graph_error ? ` (Neo4j: ${gr.graph_error.slice(0, 80)})` : " (Neo4j not configured)"}
        {" "}- used Postgres hybrid retrieval.
      </div>
    );
  return (
    <div className="panel p-3">
      <div className="flex items-center justify-between px-1">
        <div className="text-[10px] uppercase tracking-wider text-ink-500">
          Graph reasoning &middot; {gr.anchors} anchors &middot; {gr.graph_nodes_examined} nodes
          explored &middot; {gr.selected_sources} used
        </div>
        <button className="chip" onClick={() => setOpen((o) => !o)}>
          {open ? "Hide graph" : "Show graph path"}
        </button>
      </div>
      {lines.length > 0 ? (
        <ul className="mt-2 space-y-0.5 px-1 font-mono text-[11px] text-ink-300">
          {lines.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      ) : (
        <div className="mt-2 px-1 text-[11px] text-ink-500">
          Answered from the anchor symbols directly - no relationships needed.
        </div>
      )}
      {open && (
        <div className="mt-3">
          <KnowledgeGraphPanel
            versionId={versionId}
            path={gr.path}
            height={380}
            onOpenSource={onOpenArtifact}
          />
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
                Answering over <span className="text-ink-400">{repoName}</span> · session memory on
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

function WelcomeState({
  onPick,
  disabled,
  versionId,
  onOpenArtifact,
}: {
  onPick: (q: string) => void;
  disabled: boolean;
  versionId: string | null;
  onOpenArtifact: (artifactId: string) => void;
}) {
  return (
    <div className="flex flex-col items-center pt-8 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-signal-blue/15 font-mono text-lg font-bold text-signal-blue">
        C
      </div>
      <h1 className="mt-4 text-2xl font-semibold text-ink-100">Ask your repository anything</h1>
      <p className="mt-2 max-w-md text-sm text-ink-400">
        Understand code, trace impact, generate changes, or debug — answered by live execution over
        the real repository at minimum inference cost.
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
      {versionId && (
        <div className="mt-8 w-full text-left">
          <div className="mb-2 text-[10px] uppercase tracking-wider text-ink-500">
            Knowledge graph
          </div>
          <KnowledgeGraphPanel versionId={versionId} height={340} onOpenSource={onOpenArtifact} />
        </div>
      )}
    </div>
  );
}

function EmptyRepoState({ kind, name }: { kind: "none" | "not-ready"; name?: string }) {
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
