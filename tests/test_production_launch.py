"""Production launch regression coverage."""

from fastapi.testclient import TestClient

from app.config.settings import settings

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


def test_core_service_pages_have_contextual_internal_links(client: TestClient) -> None:
    expected_links = {
        "/": (
            "/ont-airport-transportation",
            "/student-airport-pickup",
            "/private-car-service",
        ),
        "/services": (
            "/ont-airport-transportation",
            "/student-airport-pickup",
            "/private-car-service",
        ),
        "/stories": (
            "/ont-airport-transportation",
            "/private-car-service",
        ),
    }

    for source_path, destination_paths in expected_links.items():
        response = client.get(source_path)
        assert response.status_code == 200
        for destination_path in destination_paths:
            assert f'href="{destination_path}"' in response.text


def test_public_trailing_slashes_redirect_directly_to_canonical_https(
    client: TestClient,
) -> None:
    canonical_base = settings.site_url.rstrip("/")
    paths = (
        "/areas",
        "/contact",
        "/gallery",
        "/quote",
        "/services",
        "/stories",
        "/vehicle",
        "/ont-airport-transportation",
        "/student-airport-pickup",
        "/private-car-service",
    )

    for path in paths:
        response = client.get(f"{path}/", follow_redirects=False)
        assert response.status_code == 308
        assert response.headers["location"] == f"{canonical_base}{path}"

        final_response = client.get(f"{path}/")
        assert final_response.status_code == 200
        assert final_response.url.path == path

    query_response = client.get("/contact/?source=seo", follow_redirects=False)
    assert query_response.headers["location"] == f"{canonical_base}/contact?source=seo"


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
