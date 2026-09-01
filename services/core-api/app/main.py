import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401 — ensure model metadata is registered
from app.config import settings
from app.database import engine
from app.middleware.request_id import RequestIdMiddleware

logger = logging.getLogger(__name__)
from app.routers import (
    agents,
    auth,
    chat,
    code,
    documents,
    health,
    jobs,
    llm,
    metrics,
    pdf,
    projects,
    rag,
    realtime,
    security,
    tools,
    usage,
    workflows,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phase 34 Path A — merged worker ($0 free tier: no separate worker service on Render Free).
    # Runs the same queue consumer as services/worker/app/worker.py:130 main()
    # inside the API process so a single Free web service handles both API + RAG ingest.
    worker_task: asyncio.Task | None = None
    if settings.environment != "test":
        try:
            # Import lazily so `pytest` without redis still collects
            from worker.worker import main as worker_main  # type: ignore

            worker_task = asyncio.create_task(worker_main())
            logger.info("[lifespan] merged worker started")
        except Exception as exc:  # worker optional — API still serves if worker fails to start
            logger.warning("[lifespan] merged worker not started: %s", exc)
            # Fallback: try `app.worker` if code was vendored into core-api (Dockerfile copy)
            try:
                from app.worker import main as app_worker_main  # type: ignore

                worker_task = asyncio.create_task(app_worker_main())
                logger.info("[lifespan] merged worker (app.worker) started")
            except Exception as exc2:
                logger.warning("[lifespan] worker fallback also failed: %s", exc2)
    yield
    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("[lifespan] merged worker stopped")
    await engine.dispose()


app = FastAPI(
    title="Nexora Core API",
    version="0.2.0",
    description="Multi-agent AI Command Center backend.",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics.router)
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(llm.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(pdf.router, prefix="/api/v1")
app.include_router(rag.router, prefix="/api/v1")
app.include_router(code.router, prefix="/api/v1")
app.include_router(realtime.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"message": "Nexora Core API", "docs": "/docs"}
