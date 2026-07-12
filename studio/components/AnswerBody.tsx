"use client";

// Lightweight, dependency-free Markdown renderer for model answers. It is
// deliberately small — fenced code blocks (with copy), inline `code`, bold,
// headings, and bullet/numbered lists — rendered as React nodes (never
// dangerouslySetInnerHTML), so answer text can never inject markup.

import { Fragment, type ReactNode } from "react";
import { CodeBlock } from "./CodeBlock";

const FENCE = /```(\w+)?\n?([\s\S]*?)```/g;

export function AnswerBody({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;

  while ((m = FENCE.exec(text)) !== null) {
    if (m.index > last) {
      blocks.push(
        <Prose key={key++} text={text.slice(last, m.index)} />,
      );
    }
    blocks.push(
      <CodeBlock key={key++} language={m[1]} code={m[2].replace(/\n$/, "")} />,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    blocks.push(<Prose key={key++} text={text.slice(last)} />);
  }

  return <div className="text-[15px] leading-relaxed text-ink-100">{blocks}</div>;
}

/** Renders non-code Markdown: headings, bullet/numbered lists, paragraphs. */
function Prose({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let key = 0;

  const flush = () => {
    if (!list) return;
    const items = list.items.map((it, i) => (
      <li key={i} className="ml-1">
        {renderInline(it)}
      </li>
    ));
    out.push(
      list.ordered ? (
        <ol key={key++} className="my-2 list-decimal space-y-1 pl-5 marker:text-ink-500">
          {items}
        </ol>
      ) : (
        <ul key={key++} className="my-2 list-disc space-y-1 pl-5 marker:text-ink-600">
          {items}
        </ul>
      ),
    );
    list = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*]\s+(.*)/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)/.exec(line);
    const heading = /^(#{1,4})\s+(.*)/.exec(line);

    if (heading) {
      flush();
      out.push(
        <h3 key={key++} className="mb-1 mt-3 text-[13px] font-semibold uppercase tracking-wide text-ink-300">
          {renderInline(heading[2])}
        </h3>,
      );
    } else if (bullet) {
      if (!list || list.ordered) {
        flush();
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
    } else if (numbered) {
      if (!list || !list.ordered) {
        flush();
        list = { ordered: true, items: [] };
      }
      list.items.push(numbered[1]);
    } else if (line.trim() === "") {
      flush();
    } else {
      flush();
      out.push(
        <p key={key++} className="my-2 first:mt-0 last:mb-0">
          {renderInline(line)}
        </p>,
      );
    }
  }
  flush();
  return <Fragment>{out}</Fragment>;
}

/** Inline: `code`, **bold**. Everything else is plain text. */
function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("`")) {
      parts.push(
        <code
          key={key++}
          className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[13px] text-signal-cyan"
        >
          {tok.slice(1, -1)}
        </code>,
      );
    } else {
      parts.push(
        <strong key={key++} className="font-semibold text-white">
          {tok.slice(2, -2)}
        </strong>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
