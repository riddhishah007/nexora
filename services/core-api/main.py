"""
Nexora Core API — Phase 1 skeleton.

This file will grow through the phases:
  Phase 4: app structure (routers, config, dependencies)
  Phase 5: auth endpoints
  Phase 6: database models + migrations
  Phase 7: LLM Gateway
  Phase 9+: orchestrator + agents

For now it only proves the container boots and can reach Postgres/Redis.
"""

import os

from fastapi import FastAPI

app = FastAPI(title="Nexora Core API", version="0.1.0")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "core-api",
        "environment": os.getenv("ENVIRONMENT", "unknown"),
    }


@app.get("/")
def root():
    return {"message": "Nexora Core API — Phase 1 skeleton is running."}
