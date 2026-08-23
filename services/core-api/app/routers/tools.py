from fastapi import APIRouter

from app.tools import get_tool_registry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools() -> list[dict]:
    """Blueprint §8: inspectable tool catalog — id, permission, trust
    level, timeout and the exact input schema the registry enforces.
    """
    registry = get_tool_registry()
    return [
        {
            "tool_id": d.tool_id,
            "name": d.name,
            "description": d.description,
            "required_permission": d.required_permission,
            "trust_level": d.trust_level,
            "timeout_seconds": d.timeout_seconds,
            "input_schema": d.input_schema,
        }
        for d in registry.definitions()
    ]
