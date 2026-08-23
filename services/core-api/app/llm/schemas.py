from dataclasses import dataclass

from pydantic import BaseModel, Field


class ModelTier:
    LITE = "lite"
    FLASH = "flash"
    PRO = "pro"

    ALL = (LITE, FLASH, PRO)


@dataclass(slots=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool = False
    mock: bool = False


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=32_000)
    tier: str = Field(default="flash", pattern="^(lite|flash|pro)$")
    system: str | None = Field(default=None, max_length=8_000)


class GenerateResponse(BaseModel):
    text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool
