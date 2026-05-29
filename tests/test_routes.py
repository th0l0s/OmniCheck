"""Smoke tests: HTTP routes return valid shapes without errors.

Uses starlette TestClient which triggers the full lifespan (scheduler starts
then is cancelled on teardown). Sources will log fetch errors (no network in CI)
but the routes themselves must succeed.
"""
import pytest
from starlette.testclient import TestClient

from cti.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_api_health_shape(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "sources" in body
    assert isinstance(body["sources"], list)
    assert "sources_ok" in body
    assert "sources_total" in body


def test_api_sources_shape(client):
    r = client.get("/api/sources")
    assert r.status_code == 200
    body = r.json()
    assert "sources" in body
    assert "version" in body
    assert isinstance(body["sources"], list)
    # every entry has at minimum id + name
    for src in body["sources"]:
        assert "id" in src
        assert "name" in src


def test_api_status_shape(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    body = r.json()
    assert "version" in body
    assert "uptime_s" in body
    assert isinstance(body.get("sources"), list)


def test_api_ui_shape(client):
    r = client.get("/api/ui")
    assert r.status_code == 200
    body = r.json()
    assert body.get("app") == "OmniCheck Cockpit"
    assert isinstance(body.get("poll_interval_s"), int)
    assert isinstance(body.get("readonly"), bool)


def test_api_targets_get(client):
    r = client.get("/api/targets")
    assert r.status_code == 200
    body = r.json()
    assert "ips" in body
    assert "domains" in body


def test_api_targets_post_requires_key(client):
    """POST /api/targets must reject requests without X-API-Key."""
    r = client.post("/api/targets", json={"add": [], "remove": []})
    # 503 if CTI_API_KEY not set; 401 if set but header missing
    assert r.status_code in (401, 503)


def test_api_data_unknown_source_404(client):
    r = client.get("/api/data/__no_such_source__")
    assert r.status_code == 404


def test_api_refresh_requires_key(client):
    """POST /api/refresh must reject without X-API-Key."""
    r = client.post("/api/refresh/bgp")
    assert r.status_code in (401, 503)
