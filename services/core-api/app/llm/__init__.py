from app.llm.gateway import build_gateway
from app.llm.schemas import GenerateRequest, GenerateResponse, LLMResponse

_gateway = None


def get_llm_gateway():
    global _gateway
    if _gateway is None:
        _gateway = build_gateway()
    return _gateway


__all__ = ["build_gateway", "get_llm_gateway", "GenerateRequest", "GenerateResponse", "LLMResponse"]
