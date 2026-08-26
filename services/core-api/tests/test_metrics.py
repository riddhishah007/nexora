"""Phase 32: metrics + request-id middleware never raises and emits expected headers."""

from fastapi.testclient import TestClient

import app.middleware.request_id as rid
from app.main import app


def test_metrics_endpoint_shape():
    c = TestClient(app)
    # hit health to increment counters
    c.get("/health")
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")
    body = r.text
    assert "nexora_http_requests_total" in body
    assert "nexora_build_info" in body
    assert 'phase="32"' in body


def test_request_id_header_present():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert "x-request-id" in {k.lower(): v for k, v in r.headers.items()}
    # value is 12 hex chars
    rid_val = r.headers.get("x-request-id") or r.headers.get("X-Request-ID")
    assert rid_val is not None and len(rid_val) == 12


def test_request_id_reuses_inbound():
    c = TestClient(app)
    r = c.get("/health", headers={"x-request-id": "abc123def456"})
    assert r.headers.get("x-request-id") == "abc123def456"


def test_metrics_counters_increment():
    # reset to known state for deterministic check
    rid.http_requests_total.clear()
    rid.http_requests_by_status.clear()
    c = TestClient(app)
    c.get("/health")
    c.get("/health")
    r = c.get("/metrics")
    # two health hits counted (metrics itself not counted until after)
    assert 'nexora_http_requests_total{route="/health",method="GET"} 2' in r.text
