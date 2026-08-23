from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import AGENT_REGISTRY
from app.llm.gateway import LLMGateway
from app.models.workflow import STEP_DONE, STEP_FAILED, STEP_RUNNING, WorkflowStep


class StepFailure(Exception):
    pass


async def execute_workflow(
    db: AsyncSession,
    steps: list[WorkflowStep],
    user_id,
) -> bool:
    """Blueprint §4 MVP executor: sequential DAG walk.

    Runs every step whose dependencies are satisfied, in seq order.
    Returns True if all steps completed. Parallel execution is Phase 14.
    """
    done: set[int] = set()
    pending = sorted(steps, key=lambda s: s.seq)
    all_ok = True

    while pending:
        runnable = [s for s in pending if set(s.depends_on) <= done]
        if not runnable:
            for s in pending:
                s.status = STEP_FAILED
                s.output = {"error": "unresolvable dependencies"}
            all_ok = False
            break

        progressed: list[int] = []
        for step in runnable:
            step.status = STEP_RUNNING
        await db.commit()

        for step in runnable:
            try:
                output, llm = await _run_step(db, step, str(user_id))
                await LLMGateway.record_usage(db, user_id, llm)
                step.output = output
                step.status = STEP_DONE
                done.add(step.seq)
            except Exception as exc:
                step.status = STEP_FAILED
                step.output = {"error": str(exc)[:500]}
                all_ok = False
            progressed.append(step.seq)
        await db.commit()
        pending = [s for s in pending if s.seq not in progressed]

    return all_ok


async def _run_step(
    db: AsyncSession, step: WorkflowStep, user_id: str
) -> tuple[dict, object]:
    agent = AGENT_REGISTRY.get(step.agent_id)
    if agent is None:
        raise StepFailure(f"agent '{step.agent_id}' not registered")

    answer, sources, llm = await agent.run(step.instruction, db, user_id=user_id)
    return (
        {
            "answer": answer,
            "sources": [
                {"title": r["title"], "url": r["url"], "score": r["score"]}
                for r in sources
            ],
            "provider": llm.provider,
            "model": llm.model,
        },
        llm,
    )
