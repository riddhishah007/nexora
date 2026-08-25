import hashlib
import json
import time
import uuid
from typing import Any, Protocol

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.api_usage  # noqa: F401
from app.config import settings
from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.mock import MockProvider
from app.llm.schemas import LLMResponse, ModelTier


class Provider(Protocol):
    async def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        response_schema: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
    ) -> LLMResponse: ...

    async def embed(self, texts: list[str], model: str) -> list[list[float]]: ...


def _cache_key(prompt: str, model: str, system: str | None) -> str:
    digest = hashlib.sha256(
        json.dumps([model, system or "", prompt]).encode("utf-8")
    ).hexdigest()
    return f"nexora:llm:{digest}"


class LLMGateway:
    """Single entry point for every LLM call in the platform.

    Blueprint §10: agents never talk to a provider directly — they call
    generate() here. Handles model-tier routing (§11), Redis response caching
    (§12), and usage accounting into api_usage.
    """

    def __init__(self, provider: Provider, redis_client: Redis | None):
        self._provider = provider
        self._redis = redis_client

    @staticmethod
    def model_for_tier(tier: str) -> str:
        if settings.llm_provider == "groq":
            return (
                settings.groq_model_lite
                if tier == ModelTier.LITE
                else settings.groq_model_pro
                if tier == ModelTier.PRO
                else settings.groq_model_flash
            )
        return (
            settings.llm_model_lite
            if tier == ModelTier.LITE
            else settings.llm_model_pro
            if tier == ModelTier.PRO
            else settings.llm_model_flash
        )

    async def _cache_get(self, key: str) -> LLMResponse | None:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
        except Exception:
            return None
        if raw is None:
            return None
        data = json.loads(raw)
        return LLMResponse(cached=True, **data)

    async def _cache_set(self, key: str, response: LLMResponse) -> None:
        if self._redis is None:
            return
        try:
            payload = {
                "text": response.text,
                "provider": response.provider,
                "model": response.model,
                "tokens_in": response.tokens_in,
                "tokens_out": response.tokens_out,
                "latency_ms": response.latency_ms,
                "mock": response.mock,
            }
            await self._redis.set(
                key, json.dumps(payload), ex=settings.llm_cache_ttl_seconds
            )
        except Exception:
            return

    async def generate(
        self,
        prompt: str,
        tier: str = ModelTier.FLASH,
        system: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        model = self.model_for_tier(tier)
        cache = (
            None if response_schema is not None else _cache_key(prompt, model, system)
        )

        if cache is not None:
            hit = await self._cache_get(cache)
            if hit is not None:
                return hit

        started = time.perf_counter()
        response = await self._provider.generate(
            prompt=prompt,
            model=model,
            system=system,
            response_schema=response_schema,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        response.latency_ms = int((time.perf_counter() - started) * 1000)

        if cache is not None:
            await self._cache_set(cache, response)
        return response

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = settings.llm_embedding_model
        return await self._provider.embed(texts, model=model)

    async def generate_stream(
        self,
        prompt: str,
        tier: str = ModelTier.FLASH,
        system: str | None = None,
    ):
        """Phase 25: token streaming. Yields visible text chunks; falls back to
        a single chunk for providers without stream support."""
        model = self.model_for_tier(tier)
        stream_fn = getattr(self._provider, "generate_stream", None)
        if stream_fn is None:
            resp = await self.generate(prompt=prompt, tier=tier, system=system)
            yield resp.text
            return
        async for chunk in stream_fn(prompt=prompt, model=model, system=system, max_output_tokens=settings.llm_max_output_tokens):
            yield chunk

    @staticmethod
    async def record_usage(
        db: AsyncSession,
        user_id: uuid.UUID | None,
        response: LLMResponse,
    ) -> None:
        from app.llm.pricing import estimate_cost
        from app.models.api_usage import ApiUsage

        db.add(
            ApiUsage(
                user_id=user_id,
                provider=response.provider,
                model=response.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                estimated_cost=estimate_cost(response.provider, response.model, response.tokens_in, response.tokens_out),
                latency_ms=response.latency_ms,
                cached=response.cached,
            )
        )
        await db.commit()


def _key_set(key: str) -> bool:
    key = key.strip()
    return bool(key) and not key.lower().startswith("your")


def build_gateway() -> LLMGateway:
    from app.llm.providers.groq import GroqProvider

    provider_name = settings.llm_provider.strip().lower()
    provider: Provider | None = None

    if provider_name == "groq" and _key_set(settings.groq_api_key):
        provider = GroqProvider(api_key=settings.groq_api_key)
    elif provider_name == "gemini" and _key_set(settings.gemini_api_key):
        provider = GeminiProvider(api_key=settings.gemini_api_key)
    elif _key_set(settings.gemini_api_key) or _key_set(settings.groq_api_key):
        # Provider requested but its key missing -> fall back to whichever
        # key exists rather than failing outright.
        provider = (
            GroqProvider(api_key=settings.groq_api_key)
            if _key_set(settings.groq_api_key)
            else GeminiProvider(api_key=settings.gemini_api_key)
        )

    if provider is None:
        if settings.environment == "development":
            provider = MockProvider()
        else:
            raise RuntimeError(
                "A provider API key (GEMINI_API_KEY or GROQ_API_KEY) is "
                "required when ENVIRONMENT != development"
            )

    redis_client: Redis | None = None
    if settings.redis_url:
        try:
            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            redis_client = None
    return LLMGateway(provider=provider, redis_client=redis_client)
