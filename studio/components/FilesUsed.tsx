"use client";

import type { UsedFile } from "@/lib/execution-insights";
import { IconFile } from "./icons";

// The exact artifacts the compiled context used. Clicking one opens its real
// source in the drawer (which also surfaces the GitHub link).
export function FilesUsed({
  files,
  onOpen,
  compact,
}: {
  files: UsedFile[];
  onOpen: (qualifiedName: string) => void;
  compact?: boolean;
}) {
  if (files.length === 0) return null;
  return (
    <ul className={compact ? "space-y-1" : "space-y-1.5"}>
      {files.map((f) => (
        <li key={f.qualifiedName}>
          <button
            onClick={() => onOpen(f.qualifiedName)}
            className="group flex w-full items-center gap-2.5 rounded-lg border border-transparent px-2 py-1.5 text-left transition-colors hover:border-ink-700 hover:bg-ink-850/60"
          >
            <IconFile className="shrink-0 text-ink-500 group-hover:text-signal-blue" />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-mono text-[12.5px] text-ink-100">
                {f.symbol}
              </span>
              <span className="block truncate font-mono text-[10.5px] text-ink-500">
                {f.path}
              </span>
            </span>
            {f.representation && (
              <span className="badge shrink-0 bg-ink-800 text-ink-400">
                {f.representation}
              </span>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}
