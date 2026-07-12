"use client";

import { useState } from "react";
import { IconCheck, IconCopy } from "./icons";

export function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1400);
        } catch {
          /* clipboard blocked — no-op */
        }
      }}
      className="btn-icon"
      title={label ?? "Copy"}
    >
      {copied ? <IconCheck className="text-signal-green" /> : <IconCopy />}
    </button>
  );
}

export function CodeBlock({
  code,
  language,
}: {
  code: string;
  language?: string;
}) {
  return (
    <div className="my-3 overflow-hidden rounded-lg border border-ink-800 bg-ink-950">
      <div className="flex items-center justify-between border-b border-ink-800 bg-ink-900/60 px-3 py-1.5">
        <span className="font-mono text-[10px] uppercase tracking-wider text-ink-500">
          {language || "code"}
        </span>
        <CopyButton text={code} label="Copy code" />
      </div>
      <pre className="overflow-x-auto px-3 py-3 text-[12.5px] leading-relaxed">
        <code className="font-mono text-ink-100">{code}</code>
      </pre>
    </div>
  );
}
