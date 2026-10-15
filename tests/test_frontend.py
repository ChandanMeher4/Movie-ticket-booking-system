"""Tests for static asset mounting and HTML page routing."""

from fastapi.testclient import TestClient


def test_serve_html_pages(client: TestClient):
    """Verify all front-end HTML routes return 200 OK with text/html content."""
    routes = [
        "/",
        "/movies.html",
        "/seats.html",
        "/bookings.html",
        "/admin.html",
        "/assistant.html",
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, f"Failed on route {route}"
        assert "text/html" in response.headers.get("content-type", "")
        assert "Cineverse" in response.text or "CINEVERSE" in response.text


def test_serve_static_assets(client: TestClient):
    """Verify CSS and JavaScript assets are accessible under /static."""
    assets = [
        "/static/css/styles.css",
        "/static/js/api.js",
        "/static/js/movies.js",
        "/static/js/seats.js",
        "/static/js/bookings.js",
        "/static/js/admin.js",
        "/static/js/assistant.js",
    ]
    for asset in assets:
        response = client.get(asset)
        assert response.status_code == 200, f"Failed on asset {asset}"
        assert len(response.text) > 100
