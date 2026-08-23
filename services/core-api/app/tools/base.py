"""Blueprint §8 tool-system primitives shared by every tool.

A tool is a small async capability with a JSON-Schema-validated input,
a declared permission (§9), a trust level (§27) and a hard timeout.
The registry is the only way agents reach tools — the security boundary
is code here, never the prompt (§25).
"""

import re
from typing import Any, Protocol

from pydantic import BaseModel, Field

TRUST_LOW = "low"  # auto-run
TRUST_MEDIUM = "medium"  # auto-run, logged
TRUST_HIGH = "high"  # requires human approval (MVP-plus, §27)

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"

_REDACTED = "[REDACTED]"

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[-_]?key|auth|token|secret|password|passwd|credential)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gsk_[A-Za-z0-9]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{16,}"),
    re.compile(r"tvly-[A-Za-z0-9]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
)
_MAX_LOGGED_STR = 2000


class ToolDefinition(BaseModel):
    """Declarative metadata enforced by the ToolRegistry before execution."""

    tool_id: str = Field(pattern="^[a-z0-9_]+$")
    name: str
    description: str
    input_schema: dict[str, Any]
    required_permission: str = Field(pattern="^[a-z]+:[a-z]+$")
    trust_level: str = TRUST_MEDIUM
    timeout_seconds: float = Field(default=15.0, gt=0)


class ToolContext(BaseModel):
    """Who is calling, on behalf of whom — checked against permissions."""

    agent_id: str
    user_id: str | None = None
    permissions: list[str] = Field(default_factory=list)

    def has_permission(self, required: str) -> bool:
        return required in self.permissions or "*:*" in self.permissions


class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    status: str = STATUS_SUCCESS
    duration_ms: int = 0
    mock: bool = False


class ToolError(Exception):
    """Base for structured tool failures (§8: never raw stack traces)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ToolNotFoundError(ToolError):
    pass


class ToolValidationError(ToolError):
    pass


class PermissionDeniedError(ToolError):
    pass


class ToolExecutionError(ToolError):
    pass


def sanitize(value: Any, _depth: int = 0) -> Any:
    """Redact obvious secrets and truncate oversized values before a
    payload is persisted to `tool_calls` (§25 sensitive-data detection).
    """
    if _depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_VALUE_PATTERNS:
            redacted = pattern.sub(_REDACTED, redacted)
        return redacted[:_MAX_LOGGED_STR]
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _SENSITIVE_KEY_PATTERN.search(key_str):
                clean[key_str] = _REDACTED
            else:
                clean[key_str] = sanitize(item, _depth + 1)
        return clean
    if isinstance(value, list):
        return [sanitize(item, _depth + 1) for item in value[:50]]
    return value


class NexoraTool(Protocol):
    """Contract every registered tool fulfils.

    `run` receives an already schema-validated input plus the caller's
    context; it returns a JSON-serializable dict or raises.
    """

    definition: ToolDefinition

    async def run(self, payload: dict[str, Any], ctx: ToolContext) -> dict[str, Any]: ...
