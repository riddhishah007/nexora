# ADR 0005 — SSE over WebSockets for Real-Time Execution Events

- **Status:** Accepted
- **Date:** 2026-08-23

## Context

The Command Center UI must render live backend events (TASK_CREATED, AGENT_STARTED,
TOOL_COMPLETED, …) during workflow runs. Options: WebSocket (bidirectional) vs SSE
(server→client stream over plain HTTP).

## Decision

Use **Server-Sent Events**: Orchestrator publishes typed JSON to Redis Pub/Sub channel
`run:{id}`; FastAPI SSE endpoint subscribes and fans out to browsers. WebSockets are
deferred until a genuinely bidirectional feature exists (e.g., collaborative editing).

## Consequences

+ Perfect fit (events are unidirectional); simpler auth over HTTP; proxy-friendly;
  built-in reconnect; less state to manage
− Client→server messages need normal REST calls (already the pattern)
