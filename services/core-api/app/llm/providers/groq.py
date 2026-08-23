import asyncio
import re
import time
from typing import Any

import httpx

from app.config import settings
from app.llm.schemas import LLMResponse

_THINK_RE = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL)


def _strip_reasoning(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


class GroqProvider:
    """OpenAI-compatible provider backed by Groq's fast inference API.

    Like GeminiProvider, this is the only module that knows this vendor's
    wire format. Uses httpx directly (no SDK dependency).
    """

    def __init__(self, api_key: str, base_url: str | None = None):
        self._api_key = api_key
        self._base_url = (
            base_url or settings.groq_base_url
        ).rstrip("/")

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        response_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_output_tokens or settings.llm_max_output_tokens,
        }
        if response_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        async with httpx.AsyncClient(
            timeout=settings.llm_request_timeout_seconds
        ) as client:
            response = await asyncio.wait_for(
                client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ),
                timeout=settings.llm_request_timeout_seconds,
            )
        latency_ms = int((time.perf_counter() - started) * 1000)

        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        choices = data.get("choices", [])
        text = ""
        if choices:
            message = choices[0].get("message") or {}
            text = message.get("content") or ""

        return LLMResponse(
            text=_strip_reasoning(text),
            provider="groq",
            model=data.get("model", model),
            tokens_in=int(usage.get("prompt_tokens", 0) or 0),
            tokens_out=int(usage.get("completion_tokens", 0) or 0),
            latency_ms=latency_ms,
        )
