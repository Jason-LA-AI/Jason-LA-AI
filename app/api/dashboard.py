"""Public pages and internal dashboard."""


from datetime import datetime, timezone
from pathlib import Path
import secrets
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo


from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session


from app.database.session import get_db_session
from app.config.settings import settings
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.order import Order
from app.models.quote import Quote
from app.schemas.manual_lead import ManualLeadCreate, ManualLeadStatusUpdate
from app.services.manual_lead_service import create_manual_lead, update_manual_lead_status



PROJECT_ROOT = Path(__file__).resolve().parents[2]

TEMPLATES_DIRECTORY = PROJECT_ROOT / "templates"

STATIC_DIRECTORY = PROJECT_ROOT / "static"

DISPLAY_TIMEZONE = ZoneInfo("America/Los_Angeles")


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIRECTORY)
)
telegram_username = (settings.telegram_username or "").lstrip("@")
templates.env.globals.update(
    phone_number=settings.phone_number,
    email_address=settings.email_address,
    telegram_username=telegram_username or None,
    telegram_url=(f"https://t.me/{telegram_username}" if telegram_username else None),
    xiaohongshu_url=settings.xiaohongshu_url,
    facebook_url=settings.facebook_url,
    site_url=settings.site_url.rstrip("/"),
)


router = APIRouter()
dashboard_security = HTTPBasic(auto_error=False)


def require_dashboard_auth(
    credentials: HTTPBasicCredentials | None = Depends(dashboard_security),
) -> None:
    """Require configured HTTP Basic credentials for the internal dashboard."""

    expected_username = settings.dashboard_username
    expected_password = settings.dashboard_password

    if not expected_username or not expected_password:
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dashboard credentials are not configured",
            )
        if not expected_username and not expected_password:
            return

    valid_credentials = bool(
        credentials
        and expected_username
        and expected_password
        and secrets.compare_digest(credentials.username, expected_username)
        and secrets.compare_digest(credentials.password, expected_password)
    )
    if not valid_credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard authentication required",
            headers={"WWW-Authenticate": 'Basic realm="Jason Dashboard"'},
        )


@router.post("/dashboard/leads", status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_dashboard_lead(
    payload: ManualLeadCreate,
    _: None = Depends(require_dashboard_auth),
    db_session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Create a manual lead without entering quote or notification flows."""

    try:
        lead = create_manual_lead(db_session, payload)
    except Exception:
        db_session.rollback()
        raise
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"lead_id": str(lead.id), "status": lead.status},
    )


@router.patch("/dashboard/leads/{lead_id}/status", include_in_schema=False)
def update_dashboard_lead_status(
    lead_id: UUID,
    payload: ManualLeadStatusUpdate,
    _: None = Depends(require_dashboard_auth),
    db_session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Immediately persist one lead status change from the dashboard."""

    lead = db_session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    try:
        update_manual_lead_status(db_session, lead, payload.status)
    except Exception:
        db_session.rollback()
        raise
    return JSONResponse(content={"lead_id": str(lead.id), "status": payload.status.value})



@router.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def home(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="home.html",
    )



@router.get(
    "/stories",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def stories_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="stories.html",
    )


@router.get(
    "/gallery",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def gallery_page(request: Request) -> HTMLResponse:
    """Render Jason's real service photo gallery."""

    return templates.TemplateResponse(request=request, name="gallery.html")



@router.get(
    "/services",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def services_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="services.html",
    )



@router.get(
    "/quote",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def quote_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="quote.html",
    )


@router.get("/quote/confirmation", response_class=HTMLResponse, include_in_schema=False)
def quote_confirmation_page(request: Request) -> HTMLResponse:
    """Show a durable acknowledgement after a booking request is saved."""
    return templates.TemplateResponse(
        request=request,
        name="quote_confirmation.html",
        context={"reference": request.query_params.get("reference")},
    )


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots() -> str:
    return f"User-agent: *\nAllow: /\nDisallow: /dashboard\nSitemap: {settings.site_url.rstrip('/')}/sitemap.xml\n"


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap() -> Response:
    base = settings.site_url.rstrip("/")
    paths = ("/", "/services", "/vehicle", "/stories", "/gallery", "/quote", "/contact", "/areas")
    urls = "".join(f"<url><loc>{base}{path}</loc></url>" for path in paths)
    return Response(
        content=f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        media_type="application/xml",
    )



@router.get(
    "/chat",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def chat_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
    )


@router.get(
    "/contact",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def contact_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="contact.html",
    )



@router.get(
    "/vehicle",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def vehicle_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="vehicle.html",
    )



@router.get(
    "/areas",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def areas_page(
    request: Request,
) -> HTMLResponse:

    return templates.TemplateResponse(
        request=request,
        name="areas.html",
    )



@router.get(
    "/dashboard",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def dashboard(
    request: Request,
    _: None = Depends(require_dashboard_auth),
    db_session: Session = Depends(get_db_session),
) -> HTMLResponse:
    """Render recent inquiries for Jason review."""

    latest_quote_id = (
        select(Quote.id)
        .join(Order, Quote.order_id == Order.id)
        .where(Order.lead_id == Lead.id)
        .order_by(Quote.version_number.desc())
        .limit(1)
        .correlate(Lead)
        .scalar_subquery()
    )
    statement = (
        select(Lead, Customer, Quote)
        .join(Customer, Lead.customer_id == Customer.id)
        .outerjoin(Quote, Quote.id == latest_quote_id)
        .order_by(Lead.received_at.desc())
        .limit(100)
    )


    rows = db_session.execute(statement).all()


    inquiries = [
        _build_inquiry_view(lead, customer, quote)
        for lead, customer, quote in rows
    ]


    response = templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "inquiries": inquiries
        },
    )


    response.headers["Cache-Control"] = "no-store"

    response.headers["X-Robots-Tag"] = "noindex, nofollow"


    return response




def _build_inquiry_view(
    lead: Lead,
    customer: Customer,
    quote: Quote | None = None,
) -> dict[str, str]:

    analysis = (
        lead.analysis_result
        if isinstance(lead.analysis_result, dict)
        else {}
    )


    extracted = analysis.get(
        "extracted_information",
        {},
    )


    if not isinstance(extracted, dict):
        extracted = {}


    return {

        "lead_id": str(lead.id),

        "source": _display_source(
            lead.source or customer.source
        ),

        "customer_name": customer.display_name or "Unknown",

        "contact": customer.primary_contact,

        "status": _dashboard_status(lead, analysis),

        "route": lead.route_summary or "Not provided",

        "suggested_price": _display_money(
            quote.suggested_amount if quote else None,
            quote.currency_code if quote else None,
            missing="Not estimated" if quote is None else "Manual review required",
        ),

        "price_range": _display_price_range(quote),

        "pricing_source": (
            quote.pricing_source or "Not provided" if quote else "Not estimated"
        ),

        "language": str(
            analysis.get("detected_language")
            or customer.preferred_language
            or "Unknown"
        ),

        "inquiry_type": str(
            analysis.get("inquiry_type")
            or _display_intent(lead.intent)
        ),

        "airport": _display_value(
            extracted.get("airport")
        ),

        "destination": _display_value(
            extracted.get("destination")
        ),

        "risk_level": str(
            analysis.get("risk_level")
            or lead.risk_level
            or "Unknown"
        ),

        "recommended_action": str(
            analysis.get("recommended_action")
            or lead.next_action
            or "Review inquiry"
        ),

        "received_time": _format_received_at(
            lead.received_at
        ),

    }



def _display_source(
    source: str | None,
) -> str:

    return {

        "XIAOHONGSHU": "Xiaohongshu",

        "FACEBOOK": "Facebook",

        "WEBSITE": "Website",

        "GOOGLE": "Google Search",

        "GOOGLE_WEBSITE": "Website",

        "REFERRAL": "Referral",

        "OTHER": "Other",

        "UNKNOWN": "Unknown",

        "PHONE": "Phone",

        "WECHAT": "WeChat",

    }.get(
        source or "UNKNOWN",
        source or "Unknown",
    )



def _display_intent(
    intent: str | None,
) -> str:

    return {

        "AIRPORT_PICKUP": "airport pickup",

        "AIRPORT_DROPOFF": "airport dropoff",

        "PRIVATE_TRANSPORTATION": "private transportation",

        "LONG_DISTANCE": "long distance",

    }.get(
        intent or "",
        "unknown",
    )


def _dashboard_status(lead: Lead, analysis: dict[str, Any]) -> str:
    manual_status = analysis.get("manual_status")
    if manual_status in {"NEW", "QUOTED", "WAITING", "CONFIRMED", "COMPLETED", "LOST"}:
        return str(manual_status)
    return {
        "NEW": "NEW",
        "QUOTED": "QUOTED",
        "AWAITING_DETAILS": "WAITING",
        "PENDING_JASON": "WAITING",
        "FOLLOW_UP": "WAITING",
        "CONVERTED": "CONFIRMED",
        "LOST": "LOST",
        "UNAVAILABLE": "LOST",
    }.get(lead.status, "NEW")



def _display_value(
    value: Any,
) -> str:

    if value is None or value == "":
        return "Not provided"

    return str(value)


def _display_money(value: Any, currency: str | None, *, missing: str) -> str:
    if value is None:
        return missing
    return f"{currency or 'USD'} {value:,.2f}"


def _display_price_range(quote: Quote | None) -> str:
    if quote is None:
        return "Not estimated"
    if quote.suggested_min_amount is None or quote.suggested_max_amount is None:
        return "Manual review required"
    currency = quote.currency_code or "USD"
    return (
        f"{currency} {quote.suggested_min_amount:,.2f}–"
        f"{quote.suggested_max_amount:,.2f}"
    )



def _format_received_at(
    received_at: datetime,
) -> str:

    value = received_at


    if value.tzinfo is None:

        value = value.replace(
            tzinfo=timezone.utc
        )


    return value.astimezone(
        DISPLAY_TIMEZONE
    ).strftime(
        "%b %d, %Y %I:%M %p %Z"
    )
