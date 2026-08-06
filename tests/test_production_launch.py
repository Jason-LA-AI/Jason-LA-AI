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


def test_social_links_are_hidden_until_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setitem(dashboard_module.templates.env.globals, "xiaohongshu_url", None)
    monkeypatch.setitem(dashboard_module.templates.env.globals, "facebook_url", None)

    home = client.get("/")
    contact = client.get("/contact")
    confirmation = client.get("/quote/confirmation")

    assert "Xiaohongshu 小红书" not in home.text
    assert "Facebook page" not in contact.text
    assert "See more real service updates" not in confirmation.text


def test_configured_social_links_render(client: TestClient, monkeypatch) -> None:
    monkeypatch.setitem(
        dashboard_module.templates.env.globals,
        "xiaohongshu_url",
        "https://example.com/xiaohongshu",
    )
    monkeypatch.setitem(
        dashboard_module.templates.env.globals,
        "facebook_url",
        "https://example.com/facebook",
    )

    for path in ("/", "/contact", "/quote/confirmation"):
        response = client.get(path)
        assert 'href="https://example.com/xiaohongshu"' in response.text
        assert 'href="https://example.com/facebook"' in response.text
