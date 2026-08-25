import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier
from app.tools import ToolContext, ToolRegistry

DATA_SYSTEM = (
    "You are the Nexora Data Agent. You analyze CSV/Excel data, generate SQL, and "
    "describe trends. Given a data summary or execution output, produce a concise "
    "analysis: Key Stats (3-5 bullets), Trends (2-3 sentences), and Recommendations. "
    "Cite the data file when relevant."
)

CODE_GEN_SYSTEM = (
    "You are a Python data analysis assistant. Given a task and a CSV file path, "
    "write Python code that reads the CSV with csv or pandas, prints key stats "
    "(shape, columns, describe, head), and handles errors gracefully. Return ONLY code."
)


class DataAgent:
    """Blueprint §5 V1 Data Agent — CSV/Excel, SQL gen, charts (MVP: csv via sandbox).

    Permissions: file:read to load the user's CSV, code:execute to run analysis.
    Flow: if document_id provided -> load CSV via file, generate pandas code via LLM,
    execute via execute_code tool, then synthesize analysis. Otherwise, just LLM.
    """

    agent_id = "data-agent"
    permissions = ["file:read", "code:execute"]

    def __init__(self, gateway: LLMGateway, registry: ToolRegistry | None = None, user_id: str | None = None):
        self._gateway = gateway
        self._tools = registry
        self._user_id = user_id

    async def run(
        self,
        task: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        document_id: str | None = None,
    ) -> tuple[str, dict, LLMResponse]:
        started = time.perf_counter()
        uid = user_id or self._user_id

        # If a CSV document is specified, try to analyze it via code execution
        file_context = ""
        exec_result = None
        stored_name: str | None = None
        if document_id and self._tools is not None and db is not None:
            # Resolve stored_name for accurate code generation
            try:
                import uuid as _uuid
                from app.models.document import Document as _Doc

                doc_uuid = _uuid.UUID(document_id)
                doc = await db.get(_Doc, doc_uuid)
                if doc is not None and str(doc.user_id) == str(uid):
                    stored_name = doc.stored_name
                    file_context = f" (data file {doc.original_filename} -> /app/storage/{stored_name})"
                else:
                    file_context = f" (data file document_id={document_id} — not found or not owned)"
                    stored_name = None
            except Exception:
                file_context = f" (data file document_id={document_id})"

            # Generate analysis code via LLM
            try:
                path_hint = f"/app/storage/{stored_name}" if stored_name else "/app/storage/<stored_name>"
                code_prompt = (
                    f"Task: {task}\n"
                    f"Document ID: {document_id or 'none'}\n"
                    f"Actual file path on disk: {path_hint}\n"
                    f"Original file: {file_context}\n"
                    "Write Python code that directly reads the CSV at the actual file path above. "
                    "The code must: import pandas as pd, df = pd.read_csv(path), print(f'Shape: {df.shape}'), "
                    "print(f'Columns: {list(df.columns)}'), print(df.describe().to_string()), print(df.head(3).to_string()). "
                    "If pandas fails, fallback to csv module. If file not found, print error with path. "
                    "No network, no extra prints."
                )
                code_llm = await self._gateway.generate(prompt=code_prompt, tier=ModelTier.FLASH, system=CODE_GEN_SYSTEM)
                # extract code fence if present
                import re
                m = re.search(r"```(?:python|py)?\s*\n?(.*?)```", code_llm.text, re.DOTALL | re.I)
                code = m.group(1).strip() if m else code_llm.text.strip()
                # execute via tool
                exec_ctx = ToolContext(agent_id=self.agent_id, user_id=uid, permissions=["code:execute"])
                res = await self._tools.execute("execute_code", {"code": code, "language": "python"}, exec_ctx, db=db)
                if res.ok:
                    exec_result = res.data
                    file_context = f"\nExecution stdout:\n{exec_result.get('stdout','')[:1500]}\nStderr:\n{exec_result.get('stderr','')[:500]}"
                else:
                    file_context = f"\nCode execution failed: {res.error}"
            except Exception as e:
                file_context = f"\nCode generation failed: {e}"

        # Synthesize analysis
        prompt = f"Task: {task}{file_context}\n\nProvide the data analysis."
        llm = await self._gateway.generate(prompt=prompt, tier=ModelTier.FLASH, system=DATA_SYSTEM)
        llm.latency_ms = int((time.perf_counter() - started) * 1000) if llm.latency_ms == 0 else llm.latency_ms

        meta = {"document_id": document_id, "execution": exec_result}
        return llm.text, meta, llm
