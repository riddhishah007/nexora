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
    input: SearchAgentInput


class AgentRunResponse(BaseModel):
    agent_id: str
    answer: str
    sources: list[Source]
    provider: str
    model: str
    latency_ms: int
    mock: bool
