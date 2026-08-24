import asyncio
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY
from app.database import SessionFactory
from app.events.bus import emit
from app.llm.gateway import LLMGateway
from app.llm.schemas import ModelTier
from app.models.workflow import STEP_DONE, STEP_FAILED, STEP_RUNNING, WorkflowStep


class StepFailure(Exception):
    pass


SYNTH_SYSTEM = (
    "You are the Nexora Synthesizer. Combine the following agent outputs into one "
    "coherent, cited answer. Each block is labeled by agent and step. Cite sources "
    "as [search:1], [rag:2], [code:1] or [pdf:1] where relevant. If outputs conflict, "
    "note the conflict. Be concise: 3-6 sentences plus a short bulleted list when helpful. "
    "If a step failed, mention it briefly."
)


async def execute_workflow(
    db: AsyncSession,
    steps: list[WorkflowStep],
    user_id,
) -> bool:
    """Blueprint §4 executor with parallel DAG walk (§14).

    Each *batch* (runnable steps whose dependencies are satisfied) runs
    concurrently via asyncio.gather. Every step in a batch gets its own
    isolated DB session (SessionFactory) so tool audit writes do not race on
    the caller's session. The caller's session is only used to flip
    step.status/output in a single commit per batch.
    """
    done: set[int] = set()
    pending = sorted(steps, key=lambda s: s.seq)
    all_ok = True
    workflow_id = str(steps[0].workflow_id) if steps else None

    if workflow_id:
        await emit(workflow_id, "WORKFLOW_STARTED", {"steps": len(steps), "user_id": str(user_id)})

    while pending:
        runnable = [s for s in pending if set(s.depends_on or []) <= done]
        if not runnable:
            for s in pending:
                s.status = STEP_FAILED
                s.output = {"error": "unresolvable dependencies (cycle or missing dep)"}
                if workflow_id:
                    await emit(workflow_id, "AGENT_FAILED", {"seq": s.seq, "agent_id": s.agent_id, "error": "unresolvable dependencies"})
            await db.commit()
            if workflow_id:
                await emit(workflow_id, "WORKFLOW_COMPLETED", {"ok": False, "reason": "unresolvable dependencies"})
            all_ok = False
            break

        for s in runnable:
            s.status = STEP_RUNNING
            if workflow_id:
                await emit(workflow_id, "AGENT_SELECTED", {"seq": s.seq, "agent_id": s.agent_id, "instruction": s.instruction})
        await db.commit()
        for s in runnable:
            if workflow_id:
                await emit(workflow_id, "AGENT_STARTED", {"seq": s.seq, "agent_id": s.agent_id})

        # Run the batch concurrently — isolated sessions inside each task.
        results = await asyncio.gather(
            *[_run_one_isolated(s.seq, s.agent_id, s.instruction, str(user_id)) for s in runnable],
            return_exceptions=True,
        )

        for step, res in zip(runnable, results):
            if isinstance(res, Exception):
                step.status = STEP_FAILED
                step.output = {"error": str(res)[:500], "agent_id": step.agent_id}
                if workflow_id:
                    await emit(workflow_id, "AGENT_FAILED", {"seq": step.seq, "agent_id": step.agent_id, "error": str(res)[:200]})
                all_ok = False
                continue
            output, llm, err = res  # type: ignore[misc]
            if err is not None:
                step.status = STEP_FAILED
                step.output = {"error": str(err)[:500], "agent_id": step.agent_id, "provider": getattr(llm, "provider", "none")}
                if workflow_id:
                    await emit(workflow_id, "AGENT_FAILED", {"seq": step.seq, "agent_id": step.agent_id, "error": str(err)[:200]})
                all_ok = False
            else:
                step.status = STEP_DONE
                step.output = output
                done.add(step.seq)
                if workflow_id:
                    await emit(workflow_id, "AGENT_COMPLETED", {"seq": step.seq, "agent_id": step.agent_id})
                # usage already recorded inside isolated session; also record on caller's session for dashboard? noop.
        await db.commit()
        pending = [s for s in pending if s.seq not in {r.seq for r in runnable}]

    if workflow_id:
        await emit(workflow_id, "WORKFLOW_COMPLETED", {"ok": all_ok, "done": len(done), "total": len(steps)})
    return all_ok


async def _run_one_isolated(seq: int, agent_id: str, instruction: str, user_id: str):
    """Run a single step in an isolated session; returns (output dict, llm, error)."""
    agent = AGENT_REGISTRY.get(agent_id)
    if agent is None:
        return None, None, StepFailure(f"agent '{agent_id}' not registered")

    # isolated session for tool audit + vector search + code exec isolation
    try:
        async with SessionFactory() as iso:
            # Dispatch by agent type (mirrors app/routers/agents.py)
            if agent_id == "search-agent":
                answer, results, llm = await agent.run(instruction, db=iso, user_id=user_id)
                await LLMGateway.record_usage(iso, user_id, llm)  # type: ignore[arg-type]
                output = {
                    "agent_id": agent_id,
                    "answer": answer,
                    "sources": [{"title": r.get("title",""), "url": r.get("url",""), "score": float(r.get("score",0))} for r in results],
                    "provider": llm.provider,
                    "model": llm.model,
                }
                return output, llm, None
            elif agent_id == "rag-agent":
                answer, citations, llm = await agent.run(instruction, db=iso, user_id=user_id)
                await LLMGateway.record_usage(iso, user_id, llm)  # type: ignore[arg-type]
                output = {
                    "agent_id": agent_id,
                    "answer": answer,
                    "citations": citations,
                    "provider": llm.provider,
                    "model": llm.model,
                }
                return output, llm, None
            elif agent_id == "pdf-agent":
                answer, meta, llm = await agent.run(instruction, db=iso, user_id=user_id)
                await LLMGateway.record_usage(iso, user_id, llm)  # type: ignore[arg-type]
                output = {"agent_id": agent_id, "answer": answer, "meta": meta, "provider": llm.provider, "model": llm.model}
                return output, llm, None
            elif agent_id == "coding-agent":
                answer, exec_data, llm = await agent.run(instruction, db=iso, user_id=user_id)
                await LLMGateway.record_usage(iso, user_id, llm)  # type: ignore[arg-type]
                output = {"agent_id": agent_id, "answer": answer, "execution": exec_data, "provider": llm.provider, "model": llm.model}
                return output, llm, None
            else:
                # generic fallback
                answer, results, llm = await agent.run(instruction, db=iso, user_id=user_id)
                await LLMGateway.record_usage(iso, user_id, llm)  # type: ignore[arg-type]
                output = {"agent_id": agent_id, "answer": answer, "provider": llm.provider, "model": llm.model}
                # try to include sources if present
                if isinstance(results, list):
                    output["sources"] = results  # type: ignore[assignment]
                return output, llm, None
    except Exception as exc:
        # Use a dummy llm for error reporting
        from app.llm.schemas import LLMResponse
        dummy = LLMResponse(text="", provider="none", model="n/a", tokens_in=0, tokens_out=0, latency_ms=0, mock=True)
        return None, dummy, exc


async def synthesize_final_answer(steps: list[WorkflowStep], user_id: str) -> tuple[str, object]:
    """If workflow has multiple successful steps, ask LLM to combine their answers (§14).

    Returns (synthesized_answer, llm_response). If only one step, returns its answer directly.
    """
    from app.llm import get_llm_gateway

    successful = [s for s in steps if s.status == STEP_DONE and s.output and s.output.get("answer")]
    if not successful:
        return "No agent produced an answer.", None  # type: ignore[return-value]
    if len(successful) == 1:
        return successful[0].output["answer"], None  # type: ignore[index]

    blocks = []
    for s in successful:
        ans = s.output.get("answer", "")[:1500]
        blocks.append(f"[Step {s.seq} — {s.agent_id}]\nInstruction: {s.instruction}\nOutput: {ans}")

    prompt = "Combine these agent results into one final answer:\n\n" + "\n\n".join(blocks)
    gateway = get_llm_gateway()
    started = time.perf_counter()
    llm = await gateway.generate(prompt=prompt, tier=ModelTier.FLASH, system=SYNTH_SYSTEM)
    llm.latency_ms = int((time.perf_counter() - started) * 1000) if llm.latency_ms == 0 else llm.latency_ms
    # Record usage — caller will handle db session
    return llm.text, llm
