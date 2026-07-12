// Pure derivations over the real execution event stream + metrics. Nothing
// here invents numbers: every value is read from an emitted event or a
// persisted metric, so the right-hand runtime panel is always measured.

import type { Execution, ExecutionEvent } from "./types";

export interface UsedFile {
  qualifiedName: string;
  path: string;
  symbol: string;
  representation?: string;
  tokens?: number;
}

/** Files/functions that made it into the compiled context (final round). */
export function filesUsed(events: ExecutionEvent[]): UsedFile[] {
  const compiled = [...events]
    .reverse()
    .find((e) => e.event_type === "CONTEXT_COMPILED");
  if (!compiled) return [];
  const included = (compiled.payload.included as
    | { qualified_name: string; representation?: string; tokens?: number }[]
    | undefined) ?? [];
  return included.map((i) => {
    const [path, ...rest] = i.qualified_name.split("::");
    return {
      qualifiedName: i.qualified_name,
      path,
      symbol: rest.join("::") || path.split("/").pop() || path,
      representation: i.representation,
      tokens: i.tokens,
    };
  });
}

/** How many candidate artifacts the retriever surfaced for evaluation. */
export function candidateCount(events: ExecutionEvent[]): number {
  return events.filter((e) => e.event_type === "CANDIDATE_FOUND").length;
}

export type Confidence = "High" | "Medium" | "Low";

/** Confidence derived from the deterministic sufficiency decisions + whether
 *  the answer itself admits missing context. Qualitative on purpose — we do
 *  not fabricate a precise percentage the runtime never measured. */
export function confidenceOf(exec: Execution): {
  level: Confidence;
  reason: string;
} {
  const answer = (exec.answer ?? "").toLowerCase();
  const admits =
    /(does not|doesn't|do not) (contain|include|have)|cannot (answer|determine|find)|no (information|mention)|not (enough|sufficient) (information|context)/.test(
      answer,
    );
  const decisions = exec.metrics?.decisions ?? [];
  const expansion = [...decisions]
    .reverse()
    .find((d) => d.operation === "context_expansion");
  const escalated = decisions.some((d) => d.decision === "ESCALATE");
  const passed = expansion?.reason?.includes("sufficiency passed");
  const roundLimit = expansion?.reason?.includes("round limit");

  if (admits)
    return { level: "Low", reason: "answer reports the context lacked the information" };
  if (roundLimit)
    return { level: "Low", reason: "sufficiency never satisfied within the round budget" };
  if (passed && !escalated)
    return { level: "High", reason: "sufficiency passed on the first compiled context" };
  if (passed && escalated)
    return { level: "Medium", reason: "sufficiency passed after one context expansion" };
  return { level: "Medium", reason: "answer produced; sufficiency signal inconclusive" };
}

export const STAGES = [
  { key: "understand", label: "Understanding question" },
  { key: "search", label: "Searching repository" },
  { key: "compile", label: "Compiling minimal context" },
  { key: "generate", label: "Generating answer" },
] as const;

export type StageKey = (typeof STAGES)[number]["key"];

const STAGE_OF: Record<string, StageKey> = {
  TASK_RECEIVED: "understand",
  TASK_PROFILED: "understand",
  REQUIREMENTS_CREATED: "understand",
  RETRIEVAL_STARTED: "search",
  CANDIDATE_FOUND: "search",
  CANDIDATE_REJECTED: "search",
  CONTEXT_DEDUPLICATED: "compile",
  CONTEXT_COMPRESSED: "compile",
  CONTEXT_COMPILED: "compile",
  PAGE_FAULT: "compile",
  PAGE_IN: "compile",
  MODEL_SELECTED: "compile",
  INFERENCE_STARTED: "generate",
  INFERENCE_COMPLETED: "generate",
  SUFFICIENCY_CHECKED: "generate",
  ESCALATION_TRIGGERED: "generate",
  EXECUTION_COMPLETED: "generate",
};

/** Index of the furthest stage reached so far (−1 if none). */
export function currentStageIndex(events: ExecutionEvent[]): number {
  let furthest = -1;
  for (const e of events) {
    const key = STAGE_OF[e.event_type];
    if (!key) continue;
    const idx = STAGES.findIndex((s) => s.key === key);
    if (idx > furthest) furthest = idx;
  }
  return furthest;
}
