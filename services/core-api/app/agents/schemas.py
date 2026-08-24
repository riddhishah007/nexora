from pydantic import BaseModel, Field

from app.llm.schemas import ModelTier


class SearchAgentInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class Source(BaseModel):
    title: str
    url: str
    score: float


class AgentInfo(BaseModel):
    agent_id: str
    name: str
    version: str
    description: str
    capabilities: list[str]
    supported_tasks: list[str]
    tools: list[str]
    permissions: list[str]
    model: str
    status: str
    cost_profile: str


class AgentRunRequest(BaseModel):
    agent_id: str = Field(pattern="^[a-z0-9-]+$")
    input: dict | SearchAgentInput = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    agent_id: str
    answer: str
    sources: list[Source] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: int
    mock: bool
    # coding-agent extra (optional, not breaking search/rag callers)
    execution: dict | None = None
    citations: list[dict] | None = None
