"""Production launch regression coverage."""

from fastapi.testclient import TestClient

from app.api import dashboard as dashboard_module


def test_seo_endpoints_and_metadata(client: TestClient) -> None:
    page = client.get("/quote")
    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")

    assert page.status_code == 200
    assert 'rel="canonical"' in page.text
    assert 'property="og:url"' in page.text
    assert 'href="/static/favicon.svg"' in page.text
    assert robots.status_code == 200
    assert "Disallow: /dashboard" in robots.text
    assert sitemap.status_code == 200
    assert "/gallery</loc>" in sitemap.text
    assert "/dashboard</loc>" not in sitemap.text


def test_confirmation_page_and_security_headers(client: TestClient) -> None:
    response = client.get("/quote/confirmation?reference=booking-123")

    assert response.status_code == 200
    assert "Your request has been received" in response.text
    assert "booking-123" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_production_dashboard_fails_closed_without_credentials(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(dashboard_module.settings, "app_environment", "production")
    monkeypatch.setattr(dashboard_module.settings, "dashboard_username", None)
    monkeypatch.setattr(dashboard_module.settings, "dashboard_password", None)

    response = client.get("/dashboard")

    assert response.status_code == 503
