import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import REGISTRY_INFO
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.workflow import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PLANNING,
    STATUS_RUNNING,
    Workflow,
    WorkflowStep,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


class StepOut(BaseModel):
    seq: int
    agent_id: str
    instruction: str
    depends_on: list[int]
    status: str
    output: dict | None


class WorkflowOut(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    steps: list[StepOut]
    definition: dict | None = None


class WorkflowCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    steps: list[dict] = Field(min_length=1, max_length=8, description="List of {agent_id, instruction, depends_on}")
    definition: dict | None = None  # frontend React Flow nodes/edges for persistence


class WorkflowCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    steps: list[StepOut]


TEMPLATES = [
    {
        "id": "template-research-rag",
        "name": "Research + RAG Synthesis",
        "description": "Search the web and your documents in parallel, then synthesize.",
        "steps": [
            {"agent_id": "search-agent", "instruction": "Search the web for the latest information about your topic", "depends_on": []},
            {"agent_id": "rag-agent", "instruction": "Answer from your ingested documents about the same topic", "depends_on": []},
        ],
    },
    {
        "id": "template-pdf-summary",
        "name": "PDF Summarization",
        "description": "Summarize an uploaded PDF with page citations.",
        "steps": [
            {"agent_id": "pdf-agent", "instruction": "Summarize the uploaded PDF (replace with your document_id)", "depends_on": []},
        ],
    },
    {
        "id": "template-code-run",
        "name": "Code Generation + Execution",
        "description": "Generate Python code and run it in the sandbox.",
        "steps": [
            {"agent_id": "coding-agent", "instruction": "Write Python code to solve the task and print the result", "depends_on": []},
        ],
    },
    {
        "id": "template-deep-research-report",
        "name": "Deep Research Report",
        "description": "Research Agent breaks the question into sub-questions and cross-checks sources; Writer turns it into a cited report.",
        "steps": [
            {"agent_id": "research-agent", "instruction": "Research the topic thoroughly with sub-questions and cross-checked sources", "depends_on": []},
            {"agent_id": "writer-agent", "instruction": "Turn the research findings into a polished markdown report with citations", "depends_on": [0]},
        ],
    },
    {
        "id": "template-csv-analysis-report",
        "name": "CSV Analysis Report",
        "description": "Data Agent analyzes your uploaded CSV in the sandbox; Writer produces an executive summary report.",
        "steps": [
            {"agent_id": "data-agent", "instruction": "Analyze the uploaded CSV (replace with your document_id): shape, stats, trends", "depends_on": []},
            {"agent_id": "writer-agent", "instruction": "Write a data analysis report from the findings with key takeaways", "depends_on": [0]},
        ],
    },
    {
        "id": "template-multi-source-brief",
        "name": "Multi-Source Brief",
        "description": "Web search, RAG, and research run in parallel; Writer merges everything into one brief.",
        "steps": [
            {"agent_id": "search-agent", "instruction": "Search the web for current information about the topic", "depends_on": []},
            {"agent_id": "rag-agent", "instruction": "Retrieve relevant passages from ingested documents about the topic", "depends_on": []},
            {"agent_id": "research-agent", "instruction": "Cross-check the topic's key claims against independent sources", "depends_on": []},
            {"agent_id": "writer-agent", "instruction": "Merge all findings into one executive brief with references", "depends_on": [0, 1, 2]},
        ],
    },
]


@router.get("/templates")
async def list_templates() -> list[dict]:
    return TEMPLATES


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowOut]:
    result = await db.execute(
        select(Workflow).where(Workflow.user_id == current_user.id).order_by(Workflow.created_at.desc()).limit(50)
    )
    workflows = result.scalars().all()
    out: list[WorkflowOut] = []
    for wf in workflows:
        steps = (
            await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == wf.id).order_by(WorkflowStep.seq))
        ).scalars().all()
        out.append(
            WorkflowOut(
                id=wf.id,
                name=wf.name,
                status=wf.status,
                steps=[
                    StepOut(seq=s.seq, agent_id=s.agent_id, instruction=s.instruction, depends_on=s.depends_on or [], status=s.status, output=s.output)
                    for s in steps
                ],
                definition=wf.definition,
            )
        )
    return out


@router.post("", response_model=WorkflowCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowCreateResponse:
    known = {a.agent_id for a in REGISTRY_INFO}
    # validate steps like planner
    for i, s in enumerate(payload.steps):
        agent_id = str(s.get("agent_id", "")).strip()
        instruction = str(s.get("instruction", "")).strip()
        if not agent_id or agent_id not in known:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"step {i}: unknown agent '{agent_id}'")
        if not instruction:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"step {i}: instruction required")
        deps = s.get("depends_on", []) or []
        for d in deps:
            if not isinstance(d, int) or d < 0 or d >= i:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"step {i}: depends_on must reference earlier steps")

    workflow = Workflow(
        user_id=current_user.id,
        name=payload.name.strip()[:200],
        status=STATUS_PLANNING,
        definition=payload.definition or {"steps": payload.steps, "name": payload.name},
    )
    db.add(workflow)
    await db.flush()

    step_rows = [
        WorkflowStep(
            workflow_id=workflow.id,
            seq=i,
            agent_id=str(s["agent_id"]).strip(),
            instruction=str(s["instruction"]).strip(),
            depends_on=s.get("depends_on", []) or [],
        )
        for i, s in enumerate(payload.steps)
    ]
    db.add_all(step_rows)
    workflow.status = STATUS_RUNNING
    # keep planning -> will be set to running, then executor will set done
    # For builder, we leave as planning until execute is called; but create with running is okay.
    # Set to planning so execute can transition to running.
    workflow.status = STATUS_PLANNING
    await db.commit()
    await db.refresh(workflow)
    for s in step_rows:
        await db.refresh(s)

    return WorkflowCreateResponse(
        id=workflow.id,
        name=workflow.name,
        status=workflow.status,
        steps=[
            StepOut(seq=s.seq, agent_id=s.agent_id, instruction=s.instruction, depends_on=s.depends_on or [], status=s.status, output=s.output)
            for s in step_rows
        ],
    )


@router.post("/{workflow_id}/execute", response_model=WorkflowOut)
async def execute_workflow_endpoint(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowOut:
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == current_user.id))
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    steps = (await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id).order_by(WorkflowStep.seq))).scalars().all()
    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow has no steps")

    # reset steps to pending if re-running
    for s in steps:
        s.status = "pending"
        s.output = None
    workflow.status = STATUS_RUNNING
    await db.commit()

    from app.orchestrator.executor import execute_workflow as run_exec, synthesize_final_answer
    from app.llm.gateway import LLMGateway

    ok = await run_exec(db, steps, current_user.id)
    workflow.status = STATUS_DONE if ok else STATUS_FAILED

    # synthesis if multiple steps
    try:
        synth_text, synth_llm = await synthesize_final_answer(steps, str(current_user.id))
        if synth_llm is not None:
            try:
                await LLMGateway.record_usage(db, current_user.id, synth_llm)
            except Exception:
                pass
            # store synthesis as extra output on workflow definition for frontend
            workflow.definition = {**(workflow.definition or {}), "synthesis": synth_text}
        elif synth_text and len(steps) > 1:
            workflow.definition = {**(workflow.definition or {}), "synthesis": synth_text}
    except Exception:
        pass

    await db.commit()
    # refresh
    steps = (await db.execute(select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id).order_by(WorkflowStep.seq))).scalars().all()
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        status=workflow.status,
        steps=[
            StepOut(seq=s.seq, agent_id=s.agent_id, instruction=s.instruction, depends_on=s.depends_on or [], status=s.status, output=s.output)
            for s in steps
        ],
        definition=workflow.definition,
    )


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(
    workflow_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkflowOut:
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == current_user.id,
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    steps = (
        (
            await db.execute(
                select(WorkflowStep)
                .where(WorkflowStep.workflow_id == workflow.id)
                .order_by(WorkflowStep.seq)
            )
        )
        .scalars()
        .all()
    )
    return WorkflowOut(
        id=workflow.id,
        name=workflow.name,
        status=workflow.status,
        steps=[
            StepOut(
                seq=s.seq,
                agent_id=s.agent_id,
                instruction=s.instruction,
                depends_on=s.depends_on or [],
                status=s.status,
                output=s.output,
            )
            for s in steps
        ],
        definition=workflow.definition,
    )
