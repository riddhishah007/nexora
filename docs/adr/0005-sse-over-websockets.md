# ADR 0005 — SSE over WebSockets for Real-Time Execution Events

- **Status:** Accepted (amended 2026-08-25 — shipped as WebSocket)
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

## Amendment (2026-08-25)

Shipped as a **WebSocket** endpoint instead: `WS /api/v1/ws/workflows/{workflow_id}`
(`app/routers/realtime.py`, Phase 15), channel `nexora:workflow:{workflow_id}`.
Reasons for deviating from the original decision:

- uvicorn's WebSocket support was already enabled for the stack; no SSE extra needed.
- Token auth via `?token=` matches the existing JWT flow; browser `EventSource`
  cannot send an Authorization header, which would have forced cookie-based auth
  (a larger change than anticipated when this ADR was written).
- The endpoint includes a DB-polling fallback (~700 ms diff events) when Redis is
  unavailable — trivially expressed in the persistent WS connection model.

The unidirectionality argument still holds: the client only sends pings. If a
genuinely bidirectional feature arrives (collaborative editing), revisit.
