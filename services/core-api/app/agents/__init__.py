from app.agents.coding_agent import CodingAgent
from app.agents.data_agent import DataAgent
from app.agents.pdf_agent import PdfAgent
from app.agents.rag_agent import RagAgent
from app.agents.research_agent import ResearchAgent
from app.agents.search_agent import SearchAgent
from app.agents.schemas import AgentInfo
from app.agents.writer_agent import WriterAgent
from app.llm import get_llm_gateway
from app.llm.gateway import LLMGateway
from app.tools import get_tool_registry

_gateway: LLMGateway = get_llm_gateway()
_tools = get_tool_registry()

search_agent = SearchAgent(gateway=_gateway, registry=_tools)
pdf_agent = PdfAgent(gateway=_gateway, registry=_tools)
rag_agent = RagAgent(gateway=_gateway, registry=_tools)
coding_agent = CodingAgent(gateway=_gateway, registry=_tools)
research_agent = ResearchAgent(gateway=_gateway, registry=_tools)
data_agent = DataAgent(gateway=_gateway, registry=_tools)
writer_agent = WriterAgent(gateway=_gateway, registry=_tools)

AGENT_REGISTRY: dict[str, object] = {
    SearchAgent.agent_id: search_agent,
    PdfAgent.agent_id: pdf_agent,
    RagAgent.agent_id: rag_agent,
    CodingAgent.agent_id: coding_agent,
    ResearchAgent.agent_id: research_agent,
    DataAgent.agent_id: data_agent,
    WriterAgent.agent_id: writer_agent,
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
    AgentInfo(
        agent_id="pdf-agent",
        name="PDF Agent",
        version="1.0.0",
        description="Reads a user-uploaded PDF and returns a page-cited summary.",
        capabilities=["pdf_parse", "text_extraction", "summarization"],
        supported_tasks=["pdf_summary", "document_review"],
        tools=["parse_pdf", "extract_text"],
        permissions=["file:read"],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="low",
    ),
    AgentInfo(
        agent_id="rag-agent",
        name="RAG Agent",
        version="1.0.0",
        description="Answers questions grounded in your ingested PDFs via pgvector retrieval with citations.",
        capabilities=["vector_search", "citation_grounding", "answer_synthesis"],
        supported_tasks=["rag_query", "document_qa", "knowledge_search"],
        tools=["search_documents"],
        permissions=["knowledge:read"],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="low",
    ),
    AgentInfo(
        agent_id="coding-agent",
        name="Coding Agent",
        version="1.0.0",
        description="Generates Python code and runs it in a sandboxed, ephemeral directory (no network, timeout + output caps).",
        capabilities=["code_generation", "code_execution", "error_explanation"],
        supported_tasks=["code_generate", "code_run", "debug"],
        tools=["execute_code"],
        permissions=["code:execute"],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="medium",
    ),
    AgentInfo(
        agent_id="research-agent",
        name="Research Agent",
        version="1.0.0",
        description="Breaks complex questions into sub-questions, searches each, cross-checks sources, and synthesizes a cited report.",
        capabilities=["subquestion_generation", "multi_search", "cross_check", "citation_synthesis"],
        supported_tasks=["research", "deep_research", "fact_check"],
        tools=["search_web"],
        permissions=["network:read"],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="low",
    ),
    AgentInfo(
        agent_id="data-agent",
        name="Data Agent",
        version="1.0.0",
        description="Analyzes CSV/Excel via pandas (shape, describe, trends) using the sandboxed code runner — cite the data file.",
        capabilities=["csv_parse", "dataframe_describe", "trend_analysis", "chart_suggest"],
        supported_tasks=["data_analysis", "csv_qa", "sql_gen"],
        tools=["execute_code"],
        permissions=["file:read", "code:execute"],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="low",
    ),
    AgentInfo(
        agent_id="writer-agent",
        name="Writer Agent",
        version="1.0.0",
        description="Produces polished markdown reports (Title, Executive Summary, Body, Takeaways, References) from prior agent outputs.",
        capabilities=["report_generation", "style_tuning", "markdown_format"],
        supported_tasks=["write_report", "summarize", "doc_gen"],
        tools=[],
        permissions=[],
        model=_gateway.model_for_tier("flash"),
        status="active",
        cost_profile="low",
    ),
]
