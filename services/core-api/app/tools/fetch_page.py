from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.security.url_guard import is_url_allowed
from app.tools.base import ToolContext, ToolDefinition, ToolExecutionError


def _is_public_ip(ip: str) -> bool:
    import ipaddress

    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


class FetchPageInput(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class FetchPageTool:
    """Blueprint §8 tool: fetch_page (Search agent's second MVP tool).

    Permission: network:read. Fetches one public URL and returns its text
    body truncated to FETCH_PAGE_MAX_BYTES. Basic SSRF guard (§25): the
    resolved IPs must be public before any request is made.
    """

    definition = ToolDefinition(
        tool_id="fetch_page",
        name="Fetch Page",
        description="Fetches a single public web page and returns its "
        "truncated text content.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "minLength": 8,
                    "maxLength": 2048,
                    "pattern": "^https?://",
                }
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        required_permission="network:read",
        trust_level="medium",
        timeout_seconds=settings.fetch_page_timeout_seconds,
    )

    async def run(
        self,
        payload: dict[str, Any],
        ctx: ToolContext,
        db: AsyncSession | None = None,
    ) -> dict[str, Any]:
        FetchPageInput.model_validate(payload)
        url = payload["url"]

        # Phase 17: SSRF guard — string + private-range check (§25)
        allowed, reason = is_url_allowed(url)
        if not allowed:
            # log blocked SSRF attempt (§26)
            if db is not None and ctx.user_id:
                try:
                    from app.security.events import log_security_event

                    await log_security_event(
                        db,
                        event_type="url_blocked",
                        risk_level="high",
                        blocked=True,
                        user_id=ctx.user_id,
                        agent_id=ctx.agent_id,
                        details={"url": url[:500], "reason": reason},
                    )
                except Exception:
                    pass
            raise ToolExecutionError(f"blocked non-public host '{self._hostname(url)}': {reason}")

        host = self._hostname(url)
        if not await self._host_is_public(host):
            if db is not None and ctx.user_id:
                try:
                    from app.security.events import log_security_event

                    await log_security_event(
                        db,
                        event_type="ssrf_blocked",
                        risk_level="high",
                        blocked=True,
                        user_id=ctx.user_id,
                        agent_id=ctx.agent_id,
                        details={"url": url[:500], "host": host, "reason": "DNS resolves to private IP"},
                    )
                except Exception:
                    pass
            raise ToolExecutionError(f"blocked non-public host '{host}' (DNS resolves to private IP)")

        async with httpx.AsyncClient(
            timeout=self.definition.timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": "NexoraAgent/0.2 (+https://nexora.example)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            raw = response.content[: settings.fetch_page_max_bytes]
            content_type = response.headers.get("content-type", "")

        return {
            "url": url,
            "status_code": response.status_code,
            "content_type": content_type,
            "text": raw.decode(response.encoding or "utf-8", errors="replace"),
            "mock": False,
        }

    @staticmethod
    def _hostname(url: str) -> str:
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""

    @staticmethod
    async def _host_is_public(host: str) -> bool:
        import asyncio
        import socket

        def resolve() -> list[str]:
            infos = socket.getaddrinfo(host, 443)
            return [info[4][0] for info in infos]

        try:
            ips = await asyncio.get_running_loop().run_in_executor(None, resolve)
        except OSError:
            return False
        return bool(ips) and all(_is_public_ip(ip) for ip in ips)
