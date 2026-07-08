// Shared execution-event stream contract (a locked architecture rule):
// the same visualization components consume either a live SSE stream from
// a running CortexOS runtime or a recorded trace exported from a real
// execution. Recorded traces are REAL executions replayed with timing —
// never fabricated.

import { API_URL } from "./api";
import type { ExecutionEvent } from "./types";

export interface ExecutionEventStream {
  readonly kind: "live" | "recorded";
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
    const source = new EventSource(
      `${API_URL}/v1/executions/${this.executionId}/stream`,
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
    return () => source.close();
  }
}

export class RecordedExecutionEventStream implements ExecutionEventStream {
  readonly kind = "recorded";

  // speed: replay time compression (recorded gaps divided by this factor)
  constructor(
    private events: ExecutionEvent[],
    private finalStatus: string = "succeeded",
    private speed: number = 8,
  ) {}

  subscribe(
    onEvent: (event: ExecutionEvent) => void,
    onDone: (status: string) => void,
  ): () => void {
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];

    const t0 = this.events.length
      ? new Date(this.events[0].ts).getTime()
      : Date.now();
    let last = 0;
    for (const event of this.events) {
      const gap = Math.min(
        (new Date(event.ts).getTime() - t0) / this.speed,
        last + 1500, // cap long silences so replays stay watchable
      );
      last = gap;
      timers.push(
        setTimeout(() => {
          if (!cancelled) onEvent(event);
        }, gap),
      );
    }
    timers.push(
      setTimeout(() => {
        if (!cancelled) onDone(this.finalStatus);
      }, last + 200),
    );
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
    };
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
] as const;
