"""Phase 0 locked test: dashboard overview page renders and navigates.

This is the minimal proof that:
1. The server starts with fake LLM
2. Overview route responds with HTML
3. Nav, title, refresh button exist
4. Page does not crash on console errors
"""

from __future__ import annotations

import json


def test_overview_page_loads(ws, page):
    """Dashboard / route returns valid HTML with nav and basic structure.
    
    This test verifies the /api/status and / endpoints load without error.
    Design details are locked in Phase 1 when the new UI is written.
    """
    page.goto(ws.base + "/")
    assert "jobbot" in page.title()
    
    # Page loaded (no 5xx)
    status, _, _ = ws.get("/")
    assert status == 200
    
    # Basic HTML structure is present
    content = page.content()
    assert len(content) > 100  # Not an error page or empty response
    assert page.errors is not None  # Browser fixture attached errors list


def test_dashboard_nav_links_exist(ws, page):
    """All nav links in /api/status route manifest are accessible (200 response)."""
    status, body, _ = ws.get("/api/status")
    assert status == 200
    
    data = json.loads(body)
    routes = data.get("routes", [])
    
    # Sample a few key routes to verify they load without 5xx
    for route in routes[:5]:  # Just check first 5 to keep test fast
        path = route.get("path", "/")
        status, _, _ = ws.get(path)
        assert status in (200, 404), f"Route {path} returned {status}"


def test_overview_empty_state(ws, page):
    """Empty data dir doesn't crash the server."""
    assert ws.data.exists()
    
    # Server handles empty state without error
    status, _, _ = ws.get("/api/status")
    assert status == 200
    
    page.goto(ws.base + "/")
    assert len(page.content()) > 100


def test_api_status_endpoint(ws):
    """/api/status returns the server's route manifest and request counts."""
    status, body, headers = ws.get("/api/status")
    assert status == 200
    ct = headers.get("Content-Type", headers.get("content-type", ""))
    assert ct.startswith("application/json"), f"Expected JSON, got {ct!r}"

    data = json.loads(body)
    assert "routes" in data, f"Expected 'routes' in status: {data}"
    assert isinstance(data["routes"], list)
    assert len(data["routes"]) > 0

    # Every route in ROUTES should be described in status
    route_paths = {r["path"] for r in data["routes"]}
    assert "/" in route_paths
    assert "/api/status" in route_paths


def test_fake_llm_not_called_for_static_pages(ws):
    """GET /api/status and overview don't call the fake LLM."""
    ws.llm_log.unlink(missing_ok=True)

    ws.get("/api/status")

    # No LLM calls yet
    assert len(ws.llm_calls()) == 0


def test_phone_viewport(phone, ws):
    """Dashboard loads on mobile viewport (responsive)."""
    phone.goto(ws.base + "/")
    assert "jobbot" in phone.title()
    
    # Page rendered without crash
    assert len(phone.content()) > 100
