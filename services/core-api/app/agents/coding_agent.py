import re
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.gateway import LLMGateway
from app.llm.schemas import LLMResponse, ModelTier
from app.tools import ToolContext, ToolRegistry

CODE_SYSTEM = (
    "You are the Nexora Coding Agent. You generate clean, runnable Python code. "
    "Return ONLY the code block (no extra prose outside the code) unless the user "
    "asked for explanation — then put explanation as comments at top. Use Python 3.12, "
    "no network calls, no file I/O outside the snippet, keep it deterministic."
)

EXPLAIN_SYSTEM = (
    "You are the Nexora Coding Agent. Explain the provided code or execution result "
    "concisely: what it does, key steps, and any errors. Cite the sandbox output when relevant."
)

_CODE_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_code(text: str) -> str:
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


class CodingAgent:
    """Blueprint §5 Coding Agent — generate + sandboxed run.

    Permissions §9: code:execute (HIGH trust §27). Every execution goes through
    ToolRegistry.execute("execute_code") so audit + timeout + output caps are
    enforced in one place, not in the prompt.
    """

    agent_id = "coding-agent"
    permissions = ["code:execute"]

    def __init__(self, gateway: LLMGateway, registry: ToolRegistry | None = None, user_id: str | None = None):
        self._gateway = gateway
        self._tools = registry
        self._user_id = user_id

    @property
    def tools(self) -> ToolContext:
        return ToolContext(agent_id=self.agent_id, user_id=self._user_id, permissions=self.permissions)

    async def generate(
        self,
        task: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
    ) -> tuple[str, LLMResponse]:
        """LLM -> code string (no execution)."""
        llm = await self._gateway.generate(prompt=task, tier=ModelTier.FLASH, system=CODE_SYSTEM)
        code = _extract_code(llm.text)
        return code, llm

    async def run(
        self,
        task: str,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        execute: bool = True,
        code: str | None = None,
    ) -> tuple[str, dict, LLMResponse]:
        """Generate (if code not supplied) -> execute via tool -> synthesize.

        Returns (answer, exec_result dict, llm_response of final synthesis).
        If execute=False, exec_result is {}.
        """
        started = time.perf_counter()
        # 1. code
        if code is None:
            code, gen_llm = await self.generate(task, db=db, user_id=user_id)
            if not code.strip():
                code = gen_llm.text.strip()
        else:
            code = code.strip()
            gen_llm = LLMResponse(text=code, provider="none", model="n/a", tokens_in=0, tokens_out=0, latency_ms=0, mock=True)

        if not execute or self._tools is None:
            # generation-only path
            return code, {}, gen_llm

        # 2. sandboxed exec
        ctx = ToolContext(agent_id=self.agent_id, user_id=user_id or self._user_id, permissions=self.permissions)
        result = await self._tools.execute("execute_code", {"code": code, "language": "python"}, ctx, db=db)
        exec_data = result.data if result.ok else {"stdout": "", "stderr": result.error or "execution failed", "exit_code": 1, "timeout": False}

        # 3. optional synthesis: if stderr/exit_code !=0, explain; else just return code + output
        if exec_data.get("exit_code", 0) != 0 or exec_data.get("stderr"):
            prompt = (
                f"Task: {task}\n\nGenerated code:\n```python\n{code}\n```\n\n"
                f"Execution result:\nexit_code={exec_data.get('exit_code')}\n"
                f"stdout:\n{exec_data.get('stdout','')[:2000]}\n"
                f"stderr:\n{exec_data.get('stderr','')[:2000]}\n\n"
                "Explain what happened and suggest a fix."
            )
            synth = await self._gateway.generate(prompt=prompt, tier=ModelTier.FLASH, system=EXPLAIN_SYSTEM)
            answer = f"```python\n{code}\n```\n\n**Execution:** exit_code={exec_data.get('exit_code')} duration={exec_data.get('duration_ms')}ms\nstdout:\n```\n{exec_data.get('stdout','')[:1500]}\n```\nstderr:\n```\n{exec_data.get('stderr','')[:1500]}\n```\n\n**Notes:** {synth.text}"
            synth.latency_ms += gen_llm.latency_ms + int((time.perf_counter() - started) * 1000)
            return answer, exec_data, synth

        answer = (
            f"```python\n{code}\n```\n\n**Execution:** exit_code={exec_data.get('exit_code')} "
            f"duration={exec_data.get('duration_ms')}ms\nstdout:\n```\n{exec_data.get('stdout','')[:1500]}\n```"
        )
        # fold timings
        gen_llm.latency_ms = int((time.perf_counter() - started) * 1000)
        return answer, exec_data, gen_llm
