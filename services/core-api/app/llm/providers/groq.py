import asyncio
import json
import re
import time
from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.llm.schemas import LLMResponse

_THINK_RE = re.compile(r"<think>.*?</think>\s*", flags=re.DOTALL | re.IGNORECASE)
_STRAY_THINK_RE = re.compile(r"</?think[^>]*>", flags=re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    # Remove closed think blocks
    text = _THINK_RE.sub("", text)
    # Remove any remaining think tags (unclosed or stray) but keep content
    # Qwen sometimes returns <think> without </think> due to truncation — strip the tags only
    text = re.sub(r"</?think[^>]*>", "", text, flags=re.IGNORECASE)
    return text.strip()


def filter_think_chunks(chunks: AsyncIterator[str]) -> AsyncIterator[str]:
    """Stream-safe <think> filter.

    Qwen emits `<think>reasoning</think>answer`. Chunks can split tags across
    boundaries, so hold back a small tail until we know whether the response
    opens with reasoning; once `</think>` is seen, pass everything through
    (minus stray tags).
    """
    started = False   # saw "<think"
    closed = False    # saw "</think>"
    buf = ""

    async def _gen() -> AsyncIterator[str]:
        nonlocal started, closed, buf
        async for ch in chunks:
            buf += ch
            low = buf.lower()
            if not closed:
                if not started:
                    i = low.find("<think")
                    if i == -1:
                        # No opener yet — flush old content, keep a tail guard
                        # long enough for a split "<think"/"</think" token.
                        if len(buf) > 32:
                            keep = 12
                            out = _STRAY_THINK_RE.sub("", buf[:-keep])
                            buf = buf[-keep:]
                            if out:
                                yield out
                        continue
                    started = True
                    buf = buf[i:]
                    low = buf.lower()
                    # fall through: the same chunk may already contain "</think>"
                # inside reasoning — drop everything until the close tag
                j = low.find("</think")
                if j == -1:
                    if len(buf) > 64:
                        buf = buf[-8:]
                    continue
                after = buf[j + 8:]
                closed = True
                buf = _STRAY_THINK_RE.sub("", after)
                continue
            out = _STRAY_THINK_RE.sub("", buf)
            buf = ""
            if out:
                yield out
        # end of stream
        if buf and not started:
            yield _STRAY_THINK_RE.sub("", buf)

    return _gen()


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

    async def generate_stream(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        max_output_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """SSE token streaming (Phase 25). Yields visible text chunks with
        <think> reasoning filtered out across chunk boundaries."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_output_tokens or settings.llm_max_output_tokens,
            "stream": True,
        }

        async def _raw() -> AsyncIterator[str]:
            # same 429 backoff policy as non-streaming generate(); safe to retry
            # because raise_for_status fires before any chunk is consumed
            for attempt in range(3):
                async with httpx.AsyncClient(timeout=settings.llm_request_timeout_seconds) as client:
                    async with client.stream(
                        "POST",
                        f"{self._base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    ) as response:
                        if response.status_code == 429 and attempt < 2:
                            retry_after = response.headers.get("retry-after")
                            try:
                                wait = float(retry_after) if retry_after else 2.0 * (attempt + 1)
                            except ValueError:
                                wait = 2.0 * (attempt + 1)
                            await asyncio.sleep(min(wait, 8.0))
                            continue
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if not data or data == "[DONE]":
                                continue
                            try:
                                obj = json.loads(data)
                            except (ValueError, TypeError):
                                continue
                            choices = obj.get("choices") or [{}]
                            delta = (choices[0].get("delta") or {}).get("content")
                            if delta:
                                yield delta
                        return

        async for chunk in filter_think_chunks(_raw()):
            yield chunk
