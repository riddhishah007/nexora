from app.agents.search_agent import SearchAgent
from app.agents.schemas import AgentInfo
from app.llm import get_llm_gateway
from app.llm.gateway import LLMGateway
from app.tools import get_tool_registry

_gateway: LLMGateway = get_llm_gateway()
_tools = get_tool_registry()

search_agent = SearchAgent(gateway=_gateway, registry=_tools)

AGENT_REGISTRY: dict[str, object] = {
    SearchAgent.agent_id: search_agent,
}

REGISTRY_INFO: list[AgentInfo] = [
    AgentInfo(
        agent_id="search-agent",
        name="Search Agent",
        version="1.1.0",
        description="Finds web sources for a query and synthesizes a cited answer.",
        capabilities=["web_search", "page_fetch", "source_ranking", "citation_extraction"],
        supported_tasks=["search", "fact_lookup"],
        tools=["search_web", "fetch_page"],
        permissions=["network:read"],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="low",
    ),
]
