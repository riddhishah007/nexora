"use client";

import * as React from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type WorkflowStreamEvent = {
  type: string;
  workflow_id?: string;
  data?: Record<string, unknown>;
};

export type StepRunStatus = "selected" | "running" | "done" | "failed" | "pending";

const EVENT_TO_STEP: Record<string, StepRunStatus> = {
  AGENT_SELECTED: "selected",
  AGENT_STARTED: "running",
  AGENT_COMPLETED: "done",
  AGENT_FAILED: "failed",
};

export type WorkflowStream = {
  connected: boolean;
  events: WorkflowStreamEvent[];
  stepStatus: Record<number, StepRunStatus>;
  workflowStatus: string | null;
  finalReady: boolean;
  error: string | null;
};

/** Subscribe to the live execution stream of a workflow (WS /ws/workflows/{id}). */
export function useWorkflowStream(workflowId: string | null, enabled: boolean): WorkflowStream {
  const [connected, setConnected] = React.useState(false);
  const [events, setEvents] = React.useState<WorkflowStreamEvent[]>([]);
  const [stepStatus, setStepStatus] = React.useState<Record<number, StepRunStatus>>({});
  const [workflowStatus, setWorkflowStatus] = React.useState<string | null>(null);
  const [finalReady, setFinalReady] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const finalReadyRef = React.useRef(false);

  React.useEffect(() => {
    if (!enabled || !workflowId) {
      setConnected(false);
      setEvents([]);
      setStepStatus({});
      setWorkflowStatus(null);
      setFinalReady(false);
      finalReadyRef.current = false;
      return;
    }
    let ws: WebSocket | null = null;
    let closedByUs = false;
    let retry = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function handle(ev: WorkflowStreamEvent) {
      setEvents((prev) => [...prev.slice(-99), ev]);
      const data = ev.data || {};
      if (ev.type === "CONNECTED") {
        const steps = Array.isArray(data.steps) ? (data.steps as { seq: number; status: string }[]) : [];
        const snap: Record<number, StepRunStatus> = {};
        for (const s of steps) {
          snap[s.seq] =
            s.status === "done"
              ? "done"
              : s.status === "failed"
                ? "failed"
                : s.status === "running"
                  ? "running"
                  : "pending";
        }
        setStepStatus(snap);
        if (typeof data.status === "string") setWorkflowStatus(data.status);
        return;
      }
      const st = EVENT_TO_STEP[ev.type];
      if (st && typeof data.seq === "number") {
        setStepStatus((prev) => ({ ...prev, [data.seq as number]: st }));
        return;
      }
      if (
        (ev.type === "WORKFLOW_STARTED" || ev.type === "WORKFLOW_COMPLETED") &&
        typeof data.status === "string"
      ) {
        setWorkflowStatus(data.status);
      } else if (ev.type === "FINAL_RESPONSE_READY") {
        setFinalReady(true);
        finalReadyRef.current = true;
      }
    }

    function connect() {
      const token = typeof window !== "undefined" ? localStorage.getItem("nexora_token") : null;
      if (!token) {
        setError("Not authenticated");
        return;
      }
      const wsBase = API_URL.replace(/^http/, "ws");
      try {
        ws = new WebSocket(`${wsBase}/ws/workflows/${workflowId}?token=${encodeURIComponent(token)}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return;
      }
      ws.onopen = () => {
        retry = 0;
        setConnected(true);
        setError(null);
      };
      ws.onmessage = (msg) => {
        try {
          handle(JSON.parse(msg.data as string) as WorkflowStreamEvent);
        } catch {}
      };
      ws.onerror = () => setError("Live stream unavailable");
      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs && !finalReadyRef.current && retry < 3) {
          retry += 1;
          retryTimer = setTimeout(connect, 800 * retry);
        }
      };
    }

    connect();
    return () => {
      closedByUs = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [workflowId, enabled]);

  return { connected, events, stepStatus, workflowStatus, finalReady, error };
}
