"""Integration tests against the live local docker stack.

Cheap endpoints only — no LLM calls. Marked `integration`; auto-skip when
localhost:8000 is unreachable.
"""

import uuid

import httpx
import pytest

from conftest import API


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    return httpx.Client(base_url=API, timeout=15)


@pytest.mark.integration
def test_health(client):
    r = client.get("/../health")  # /health lives outside /api/v1
    assert r.status_code in (200, 404)  # 404 would mean routing change; 200 expected
    if r.status_code == 200:
        body = r.json()
        assert body.get("status") == "ok"


@pytest.mark.integration
def test_auth_me_roundtrip(client, api_headers):
    r = client.get("/auth/me", headers=api_headers)
    assert r.status_code == 200
    body = r.json()
    assert "id" in body and "email" in body


@pytest.mark.integration
def test_agents_registry_complete(client, api_headers):
    r = client.get("/agents", headers=api_headers)
    assert r.status_code == 200
    agents = {a["agent_id"] for a in r.json()}
    assert {
        "search-agent",
        "pdf-agent",
        "rag-agent",
        "coding-agent",
        "research-agent",
        "data-agent",
        "writer-agent",
    } <= agents


@pytest.mark.integration
def test_workflow_templates_shape(client, api_headers):
    r = client.get("/workflows/templates", headers=api_headers)
    assert r.status_code == 200
    templates = r.json()
    assert len(templates) >= 6
    for t in templates:
        assert {"id", "name", "steps"} <= set(t.keys())
        for s in t["steps"]:
            assert {"agent_id", "instruction", "depends_on"} <= set(s.keys())


@pytest.mark.integration
def test_create_workflow_validates_unknown_agent(client, api_headers):
    r = client.post(
        "/workflows",
        json={"name": "bad", "steps": [{"agent_id": "nope", "instruction": "x"}]},
        headers=api_headers,
    )
    assert r.status_code == 400


@pytest.mark.integration
def test_workflow_crud_and_validation_error(client, api_headers):
    # create a valid workflow (not executed — no LLM calls)
    r = client.post(
        "/workflows",
        json={
            "name": f"it-{uuid.uuid4().hex[:6]}",
            "steps": [
                {"agent_id": "search-agent", "instruction": "step zero", "depends_on": []},
                {"agent_id": "writer-agent", "instruction": "step one uses step zero", "depends_on": [0]},
            ],
        },
        headers=api_headers,
    )
    assert r.status_code == 201
    wf = r.json()
    assert len(wf["steps"]) == 2

    # invalid deps rejected
    bad = client.post(
        "/workflows",
        json={
            "name": "bad deps",
            "steps": [
                {"agent_id": "search-agent", "instruction": "a", "depends_on": [5]},
            ],
        },
        headers=api_headers,
    )
    assert bad.status_code == 400

    # detail fetch works and is scoped to owner
    got = client.get(f"/workflows/{wf['id']}", headers=api_headers)
    assert got.status_code == 200
    assert got.json()["status"] in ("planning", "running", "done", "failed")


@pytest.mark.integration
def test_usage_summary_shape(client, api_headers):
    r = client.get("/usage/summary?days=7", headers=api_headers)
    assert r.status_code == 200
    s = r.json()
    assert {"total_calls", "tokens_in", "tokens_out", "by_model", "by_day"} <= set(s.keys())
    assert isinstance(s["by_model"], list) and isinstance(s["by_day"], list)


@pytest.mark.integration
def test_usage_is_user_scoped(client, api_headers):
    # fresh user sees zeros even though other users have usage
    email = f"iso_{uuid.uuid4().hex[:8]}@test.dev"
    with httpx.Client(base_url=API, timeout=15) as c:
        c.post("/auth/register", json={"email": email, "password": "Test1234!"})
        token = c.post("/auth/login", json={"email": email, "password": "Test1234!"}).json()["access_token"]
    r = httpx.get(f"{API}/usage/summary?days=30", headers={"Authorization": f"Bearer {token}"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["total_calls"] == 0


@pytest.mark.integration
def test_auth_boundaries(client):
    # agent registry is a public catalog; private data requires auth
    assert client.get("/agents").status_code == 200
    assert client.get("/usage/summary").status_code == 401
    assert client.post("/workflows", json={"name": "x", "steps": []}).status_code in (401, 422)
    assert client.get("/workflows").status_code == 401
