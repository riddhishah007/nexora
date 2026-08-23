import asyncio
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.llm.schemas import LLMResponse


class GeminiProvider:
    """Calls Google Gemini through the google-genai async client.

    This is the only module in the codebase that knows the provider SDK.
    """

    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        response_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens or settings.llm_max_output_tokens,
            system_instruction=system,
        )
        if response_schema is not None:
            config.response_mime_type = "application/json"

        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=model, contents=prompt, config=config
            ),
            timeout=settings.llm_request_timeout_seconds,
        )

        usage = response.usage_metadata
        return LLMResponse(
            text=response.text or "",
            provider="gemini",
            model=model,
            tokens_in=getattr(usage, "prompt_token_count", 0) or 0,
            tokens_out=getattr(usage, "candidates_token_count", 0) or 0,
            latency_ms=0,
        )
