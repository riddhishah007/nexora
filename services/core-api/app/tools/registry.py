"""Blueprint §8 ToolRegistry: the single gateway between agents and tools.

Every call flows through execute():
  schema validation -> permission check (§9) -> handler under a hard
  timeout -> sanitized audit row in `tool_calls` -> structured result.
Malformed plans or prompts cannot widen an agent's powers: the boundary
is this module, not the LLM.
"""

import asyncio
import json
import time
import uuid

from jsonschema import ValidationError as JsonSchemaError
from jsonschema import validate as jsonschema_validate
from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.base import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_SUCCESS,
    NexoraTool,
    PermissionDeniedError,
    ToolContext,
    ToolDefinition,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolResult,
    ToolValidationError,
    sanitize,
)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, NexoraTool] = {}

    def register(self, tool: NexoraTool, replace: bool = False) -> None:
        tool_id = tool.definition.tool_id
        if tool_id in self._tools and not replace:
            raise ToolError(f"tool '{tool_id}' already registered")
        self._tools[tool_id] = tool

    def get(self, tool_id: str) -> NexoraTool:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(f"unknown tool '{tool_id}'")
        return tool

    def definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    @staticmethod
    def _validate_input(tool: NexoraTool, payload: dict) -> None:
        try:
            jsonschema_validate(payload or {}, tool.definition.input_schema)
        except JsonSchemaError as exc:
            raise ToolValidationError(
                f"input for '{tool.definition.tool_id}' failed schema "
                f"validation: {exc.message}"
            ) from None

    async def execute(
        self,
        tool_id: str,
        payload: dict,
        ctx: ToolContext,
        db: AsyncSession | None = None,
    ) -> ToolResult:
        """Validate -> authorize -> run -> audit. Never raises ToolError;
        failures come back as structured results the orchestrator can
        inspect and retry (§8).
        """
        started = time.perf_counter()

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started) * 1000)

        try:
            tool = self.get(tool_id)
        except ToolNotFoundError as exc:
            return ToolResult(ok=False, error=exc.message, status=STATUS_FAILED)

        if not ctx.has_permission(tool.definition.required_permission):
            await self._audit(
                db, ctx, tool.definition, STATUS_BLOCKED,
                input_payload=payload,
                error="permission denied", duration_ms=elapsed_ms(),
            )
            raise PermissionDeniedError(
                f"agent '{ctx.agent_id}' lacks permission "
                f"'{tool.definition.required_permission}' for tool '{tool_id}'"
            )

        try:
            self._validate_input(tool, payload)
        except ToolValidationError as exc:
            await self._audit(
                db, ctx, tool.definition, STATUS_FAILED,
                input_payload=payload, error=exc.message,
                duration_ms=elapsed_ms(),
            )
            return ToolResult(ok=False, error=exc.message, status=STATUS_FAILED)

        try:
            data = await asyncio.wait_for(
                tool.run(payload or {}, ctx, db=db),
                timeout=tool.definition.timeout_seconds,
            )
        except asyncio.TimeoutError:
            error = (
                f"tool '{tool_id}' exceeded "
                f"{tool.definition.timeout_seconds:.0f}s timeout"
            )
            await self._audit(
                db, ctx, tool.definition, STATUS_FAILED,
                input_payload=payload, error=error,
                duration_ms=elapsed_ms(),
            )
            return ToolResult(ok=False, error=error, status=STATUS_FAILED)
        except Exception as exc:
            detail = f"{exc}".strip() or type(exc).__name__
            error = f"tool '{tool_id}' execution failed: {detail}"[:500]
            await self._audit(
                db, ctx, tool.definition, STATUS_FAILED,
                input_payload=payload, error=error,
                duration_ms=elapsed_ms(),
            )
            return ToolResult(ok=False, error=error, status=STATUS_FAILED)

        result = ToolResult(
            ok=True, data=data, status=STATUS_SUCCESS, duration_ms=elapsed_ms()
        )
        await self._audit(
            db, ctx, tool.definition, STATUS_SUCCESS,
            input_payload=payload, output_payload=data,
            duration_ms=result.duration_ms,
        )
        return result

    @staticmethod
    async def _audit(
        db: AsyncSession | None,
        ctx: ToolContext,
        definition: ToolDefinition,
        status: str,
        *,
        input_payload: dict | None = None,
        output_payload: dict | None = None,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> None:
        """Persist a sanitized row to `tool_calls`; audit failure must not
        break execution, so it is swallowed after a server-side print.
        """
        from app.models.tool_call import ToolCall

        if db is None:
            return
        row = ToolCall(
            user_id=None,
            agent_id=ctx.agent_id[:64],
            tool_id=definition.tool_id,
            status=status,
            input=json.loads(json.dumps(sanitize(input_payload or {}))),
            output=(
                json.loads(json.dumps(sanitize(output_payload)))
                if output_payload is not None
                else None
            ),
            error=(error[:500] if error else None),
            duration_ms=duration_ms,
        )
        if ctx.user_id:
            try:
                row.user_id = uuid.UUID(ctx.user_id)
            except ValueError:
                row.user_id = None
        try:
            db.add(row)
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — audit is best-effort here
            print(f"[tools] audit write failed: {type(exc).__name__}: {exc}")


def build_registry() -> ToolRegistry:
    from app.tools.execute_code import ExecuteCodeTool
    from app.tools.extract_text import ExtractTextTool
    from app.tools.fetch_page import FetchPageTool
    from app.tools.parse_pdf import ParsePdfTool
    from app.tools.search_documents import SearchDocumentsTool
    from app.tools.search_web import SearchWebTool

    registry = ToolRegistry()
    registry.register(SearchWebTool())
    registry.register(FetchPageTool())
    registry.register(ParsePdfTool())
    registry.register(ExtractTextTool())
    registry.register(SearchDocumentsTool())
    registry.register(ExecuteCodeTool())
    return registry


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry
