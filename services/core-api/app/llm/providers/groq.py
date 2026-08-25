import asyncio
import re
import time
from typing import Any

import httpx

from app.config import settings
from app.llm.schemas import LLMResponse

_THINK_RE = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL | re.IGNORECASE)

def _strip_reasoning(text: str) -> str:
    # Remove closed think blocks
    text = _THINK_RE.sub("", text)
    # Remove any remaining think tags (unclosed or stray) but keep content
    # Qwen sometimes returns <think> without </think> due to truncation — strip the tags only
    text = re.sub(r"</?think[^>]*>", "", text, flags=re.IGNORECASE)
    return text.strip()


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

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        # Groq has no embedding endpoint — use a deterministic local hash
        # so RAG still works when LLM_PROVIDER=groq (blueprint §10). The
        # same algorithm is used by MockProvider; real embeddings come from
        # Gemini when that provider is selected.
        import hashlib as _hashlib

        out: list[list[float]] = []
        for text in texts:
            digest = _hashlib.sha256(text.encode("utf-8")).digest()
            vec = [((digest[i % len(digest)] - 128) / 128.0) for i in range(768)]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out

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

        # Simple 429 retry with backoff (Phase 14 parallel bursts hit free-tier limits)
        last_exc: Exception | None = None
        for attempt in range(3):
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
            if response.status_code == 429 and attempt < 2:
                # respect Retry-After if present, else exponential backoff 2s, 4s
                retry_after = response.headers.get("retry-after")
                try:
                    wait = float(retry_after) if retry_after else (2.0 * (attempt + 1))
                except ValueError:
                    wait = 2.0 * (attempt + 1)
                await asyncio.sleep(min(wait, 8.0))
                last_exc = None
                continue
            response.raise_for_status()
            break
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
