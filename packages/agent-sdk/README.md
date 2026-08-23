# agent-sdk

Shared code used by every agent in Nexora, so adding a new agent never
requires touching the Orchestrator (see Blueprint §6 — Agent Registry).

This will hold, starting in Phase 9:
- The `Agent` base interface (`async def run(task: Task) -> AgentResult`)
- Shared `Task` / `AgentResult` data models
- The `Tool` interface and `ToolRegistry` client used by agents to call tools

Empty for now — populated in Phase 9 (Orchestrator) and Phase 10 (Tool System).
