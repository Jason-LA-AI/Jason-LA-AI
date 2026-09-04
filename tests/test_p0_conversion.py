"""Regression coverage for mobile navigation and direct-contact conversion paths."""

from fastapi.testclient import TestClient

from app.api import dashboard as dashboard_module


def test_mobile_navigation_keeps_primary_and_service_links(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert 'class="nav-toggle"' in response.text
    assert 'aria-expanded="false"' in response.text
    assert 'aria-controls="main-menu"' in response.text
    assert 'class="menu-primary"' in response.text
    assert 'class="menu-secondary"' in response.text
    for path in (
        "/",
        "/services",
        "/stories",
        "/quote",
        "/contact",
        "/ont-airport-transportation",
        "/student-airport-pickup",
        "/private-car-service",
        "/vehicle",
        "/gallery",
        "/areas",
    ):
        assert f'href="{path}"' in response.text
    assert 'src="/static/nav.js?v=20260904-1"' in response.text


def test_phone_call_and_text_links_are_conditional(client: TestClient, monkeypatch) -> None:
    monkeypatch.setitem(dashboard_module.templates.env.globals, "phone_number", None)
    without_phone = client.get("/contact")
    assert 'href="tel:' not in without_phone.text
    assert 'href="sms:' not in without_phone.text

    monkeypatch.setitem(dashboard_module.templates.env.globals, "phone_number", "+16265550123")
    home = client.get("/")
    assert 'href="tel:' not in home.text
    assert 'href="sms:' not in home.text
    assert 'href="/quote">Get a Quote</a>' in home.text
    assert 'href="/contact">Contact Jason</a>' in home.text

    for path in ("/contact", "/quote", "/quote/confirmation"):
        response = client.get(path)
        assert 'href="tel:+16265550123"' in response.text
        assert 'href="sms:+16265550123"' in response.text

    quote = client.get("/quote")
    assert 'id="estimateErrorContact"' in quote.text


def test_wechat_id_only_renders_when_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setitem(dashboard_module.templates.env.globals, "wechat_id", None)
    assert "WeChat ID:" not in client.get("/contact").text

    monkeypatch.setitem(dashboard_module.templates.env.globals, "wechat_id", "configured-wechat")
    response = client.get("/contact")
    assert "WeChat ID: <strong>configured-wechat</strong>" in response.text
    assert 'data-copy-value="configured-wechat"' in response.text


def test_line_link_or_id_renders_only_when_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setitem(dashboard_module.templates.env.globals, "line_url", None)
    monkeypatch.setitem(dashboard_module.templates.env.globals, "line_id", None)
    unconfigured = client.get("/contact")
    assert "Open LINE" not in unconfigured.text
    assert "LINE ID:" not in unconfigured.text

    monkeypatch.setitem(dashboard_module.templates.env.globals, "line_id", "configured-line")
    id_response = client.get("/contact")
    assert "LINE ID: <strong>configured-line</strong>" in id_response.text
    assert 'data-copy-value="configured-line"' in id_response.text

    monkeypatch.setitem(dashboard_module.templates.env.globals, "line_url", "https://line.me/example")
    url_response = client.get("/contact")
    assert 'href="https://line.me/example"' in url_response.text
    assert "Open LINE" in url_response.text
    assert "LINE ID:" not in url_response.text


def test_quote_uses_preliminary_fare_wording_and_contact_fallback(client: TestClient) -> None:
    response = client.get("/quote")

    assert response.status_code == 200
    assert "Estimated Fare Range" in response.text
    assert "This is a preliminary planning range." in response.text
    assert "before confirming the final fare" in response.text
    assert "development_mock" not in response.text
    assert 'id="estimateErrorContact"' in response.text
    assert 'href="/contact">Contact Jason' in response.text


def test_service_pages_offer_quote_and_contact(client: TestClient) -> None:
    for path in (
        "/",
        "/ont-airport-transportation",
        "/student-airport-pickup",
        "/private-car-service",
        "/stories",
        "/quote",
        "/contact",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert 'href="/quote"' in response.text
        assert 'href="/contact"' in response.text
