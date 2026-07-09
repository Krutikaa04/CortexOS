"use client";

// Add a repository to the knowledge layer: paste a Git URL (or a path
// visible inside the runtime containers) and CortexOS clones, parses,
// links, and embeds it. Hidden in demo mode — there is no live runtime
// to ingest into on the public deployment.

import { useState } from "react";
import { api } from "@/lib/api";
//import { api, DEMO_MODE } from "@/lib/api";

export function AddSourceForm({ onQueued }: { onQueued: () => void }) {
  const [uri, setUri] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // if (DEMO_MODE) return null;

  const submit = async () => {
    const trimmed = uri.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.ingestSource(trimmed);
      setNotice(
        "Ingestion queued — cloning, parsing, and embedding. The source " +
          "appears below and flips to READY when done.",
      );
      setUri("");
      onQueued();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

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
      <p className="mt-2 text-[11px] leading-relaxed text-ink-500">
        Any public Git URL works. For a local folder: make it a Git repo
        (<code className="rounded bg-ink-800 px-1">git init && git add -A && git commit</code>),
        mount its parent directory into the containers in{" "}
        <code className="rounded bg-ink-800 px-1">docker-compose.dev.yml</code>, and paste
        the container-side path (e.g.{" "}
        <code className="rounded bg-ink-800 px-1">/data/local/my-project</code>).
      </p>
      {notice && <p className="mt-2 text-xs text-signal-green">{notice}</p>}
      {error && <p className="mt-2 text-xs text-signal-red">{error}</p>}
    </div>
  );
}
