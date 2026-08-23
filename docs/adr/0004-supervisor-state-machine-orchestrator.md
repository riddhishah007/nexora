# ADR 0004 — Hand-Built Supervisor + State-Machine Orchestrator

- **Status:** Accepted
- **Date:** 2026-08-23

## Context

Evaluated patterns: pure supervisor, planner/executor, hierarchical agents, graph
frameworks (LangGraph), state machines, event-driven execution. Requirements:
dynamic agent selection via registry, resumability, parallel fan-out, testability,
and full learning/portfolio ownership of the core engine.

## Decision

Hybrid, hand-built (~small, no framework lock-in): **Supervisor** selects agents
dynamically from the registry → Planner emits a task DAG as structured output → plan
is persisted as rows (`workflows`, `workflow_steps`) forming an explicit **state
machine** → Execution Engine runs any step whose dependencies are satisfied
(sequential or parallel) → each step spawns an AgentRun whose output is schema-
validated (repair-retry ×2, else graceful fail) → events published at every transition
→ Synthesizer merges results. Frameworks like LangGraph rejected: heavy dependency,
hides internals we want to own and demonstrate.

## Consequences

+ Deterministic, inspectable, resumable runs; plans are queryable data, not logs
+ Adding an agent never touches the orchestrator (registry-driven discovery)
− We own edge cases a framework might solve for us (accepted deliberately)
