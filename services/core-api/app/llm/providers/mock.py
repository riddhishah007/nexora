import hashlib

from app.llm.schemas import LLMResponse, ModelTier


class MockProvider:
    """Deterministic offline provider used only in development when no
    GEMINI_API_KEY is configured. Keeps the gateway pipeline (routing,
    caching, usage logging) testable without spending tokens."""

    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        response_schema: dict | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        _ = (system, response_schema, max_output_tokens)
        tier = (
            ModelTier.LITE
            if "lite" in model
            else ModelTier.PRO if "pro" in model else ModelTier.FLASH
        )
        text = (
            f"[MOCK:{model}|tier={tier}] Received {len(prompt)} chars."
        )
        return LLMResponse(
            text=text,
            provider="mock",
            model=model,
            tokens_in=max(1, len(prompt) // 4),
            tokens_out=max(1, len(text) // 4),
            latency_ms=0,
            mock=True,
        )

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vec = [((digest[i % len(digest)] - 128) / 128.0) for i in range(768)]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out
