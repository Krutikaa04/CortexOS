// Execution-event stream contract: the visualization components consume a
// live SSE stream from a running CortexOS runtime. Every event is a fact
// about a real execution as it happens — never fabricated, never replayed.

import { API_URL, authHeaders } from "./api";
import type { ExecutionEvent } from "./types";

export interface ExecutionEventStream {
  readonly kind: "live";
  subscribe(
    onEvent: (event: ExecutionEvent) => void,
    onDone: (status: string) => void,
    onError?: (error: Error) => void,
  ): () => void; // returns unsubscribe
}

export class LiveExecutionEventStream implements ExecutionEventStream {
  readonly kind = "live";

  constructor(private executionId: string) {}

  subscribe(
    onEvent: (event: ExecutionEvent) => void,
    onDone: (status: string) => void,
    onError?: (error: Error) => void,
  ): () => void {
    let closed = false;
    let source: EventSource | null = null;
    // EventSource cannot send an Authorization header, so an authenticated
    // POST first obtains a short-lived ticket bound to this execution.
    fetch(`${API_URL}/v1/executions/${this.executionId}/stream-ticket`, {
      method: "POST",
      headers: authHeaders(),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`stream ticket: HTTP ${r.status}`);
        return r.json() as Promise<{ ticket: string }>;
      })
      .then(({ ticket }) => {
        if (closed) return;
        source = this.open(ticket, onEvent, onDone, onError);
      })
      .catch((e) => !closed && onError?.(e instanceof Error ? e : new Error(String(e))));
    return () => {
      closed = true;
      source?.close();
    };
  }

  private open(
    ticket: string,
    onEvent: (event: ExecutionEvent) => void,
    onDone: (status: string) => void,
    onError?: (error: Error) => void,
  ): EventSource {
    const source = new EventSource(
      `${API_URL}/v1/executions/${this.executionId}/stream?ticket=${encodeURIComponent(ticket)}`,
    );
    source.onmessage = () => {}; // typed events only
    const handler = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      onEvent(data as ExecutionEvent);
    };
    // Register for every known event type via a catch-all: EventSource has
    // no wildcard, so the server sends the type in the payload too and we
    // listen on all types we know about.
    for (const type of EVENT_TYPES) {
      source.addEventListener(type, handler);
    }
    source.addEventListener("DONE", (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      source.close();
      onDone(data.status);
    });
    source.onerror = () => {
      source.close();
      onError?.(new Error("event stream disconnected"));
    };
    return source;
  }
}

const EVENT_TYPES = [
  "TASK_RECEIVED",
  "TASK_PROFILED",
  "REQUIREMENTS_CREATED",
  "RETRIEVAL_STARTED",
  "CANDIDATE_FOUND",
  "CANDIDATE_REJECTED",
  "CONTEXT_DEDUPLICATED",
  "CONTEXT_COMPRESSED",
  "CONTEXT_COMPILED",
  "MODEL_SELECTED",
  "INFERENCE_STARTED",
  "INFERENCE_COMPLETED",
  "PAGE_FAULT",
  "PAGE_IN",
  "PAGE_OUT",
  "EVICT",
  "PIN",
  "INVALIDATE",
  "SUFFICIENCY_CHECKED",
  "ESCALATION_TRIGGERED",
  "EXECUTION_COMPLETED",
  "EXECUTION_FAILED",
  "IMPACT_STARTED",
  "IMPACT_DIFF_PARSED",
  "IMPACT_ARTIFACTS_RESOLVED",
  "IMPACT_BLAST_RADIUS",
  "IMPACT_RISK_SCORED",
  "IMPACT_EVIDENCE_COMPILED",
  "IMPACT_NARRATIVE",
  "IMPACT_COMPLETED",
] as const;
