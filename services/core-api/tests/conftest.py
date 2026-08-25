"""Shared fixtures. Unit tests import app modules directly (run inside the
core-api container where cwd=/app). Integration tests talk HTTP to the live
stack and skip automatically when it is unreachable."""

import httpx
import pytest

BASE_URL = "http://localhost:8000"
API = f"{BASE_URL}/api/v1"

_stack_up: bool | None = None


def _stack_reachable() -> bool:
    global _stack_up
    if _stack_up is None:
        try:
            httpx.get(f"{BASE_URL}/health", timeout=3)
            _stack_up = True
        except Exception:
            _stack_up = False
    return _stack_up


@pytest.fixture(scope="session")
def api_headers() -> dict:
    """Authenticated headers for a throwaway integration-test user."""
    if not _stack_reachable():
        pytest.skip("live stack not reachable")
    import uuid as _uuid

    email = f"it_{_uuid.uuid4().hex[:10]}@test.dev"
    with httpx.Client(base_url=API, timeout=15) as c:
        c.post("/auth/register", json={"email": email, "password": "Test1234!"})
        r = c.post("/auth/login", json={"email": email, "password": "Test1234!"})
        token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
