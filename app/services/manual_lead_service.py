"""Create manual leads without invoking quote or notification workflows."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.lead import Lead
from app.schemas.manual_lead import ManualLeadCreate, ManualLeadStatus


DATABASE_STATUS_BY_MANUAL_STATUS = {
    "NEW": "NEW",
    "QUOTED": "QUOTED",
    "WAITING": "FOLLOW_UP",
    "CONFIRMED": "CONVERTED",
    "COMPLETED": "CONVERTED",
    "LOST": "LOST",
}


def create_manual_lead(db: Session, request: ManualLeadCreate) -> Lead:
    """Persist one customer and lead from dashboard-entered information."""

    source = request.source.value
    primary_contact, primary_contact_type = _primary_contact(request)
    now = datetime.now(timezone.utc)
    customer = Customer(
        display_name=request.customer_name,
        primary_contact=primary_contact,
        primary_contact_type=primary_contact_type,
        phone_number=request.phone,
        preferred_contact_method=primary_contact_type,
        source=source,
        communication_notes=request.notes,
        last_contact_at=now,
    )
    db.add(customer)
    db.flush()

    airport = request.airport.upper() if request.airport else None
    extracted = {
        key: value
        for key, value in {
            "airport": airport,
            "pickup": request.pickup,
            "destination": request.destination,
            "service_date": request.service_date,
        }.items()
        if value
    }
    route_summary = " → ".join(
        value for value in (request.pickup, airport, request.destination) if value
    ) or None
    lead = Lead(
        customer_id=customer.id,
        source=source,
        intent=request.intent.value if request.intent else None,
        status=DATABASE_STATUS_BY_MANUAL_STATUS[request.status.value],
        received_at=now,
        last_contact_at=now,
        next_action="REVIEW_MANUAL_LEAD",
        next_action_owner="JASON",
        analysis_result={
            "extracted_information": extracted,
            "manual_status": request.status.value,
        },
        customer_message_summary=request.notes,
        route_summary=route_summary,
        intake_method="MANUAL",
    )
    db.add(lead)
    db.flush()
    db.commit()
    return lead


def update_manual_lead_status(
    db: Session,
    lead: Lead,
    status: ManualLeadStatus,
) -> Lead:
    """Persist a dashboard status using existing Lead columns only."""

    analysis = dict(lead.analysis_result) if isinstance(lead.analysis_result, dict) else {}
    analysis["manual_status"] = status.value
    lead.analysis_result = analysis
    lead.status = DATABASE_STATUS_BY_MANUAL_STATUS[status.value]
    db.add(lead)
    db.commit()
    return lead


def _primary_contact(request: ManualLeadCreate) -> tuple[str, str]:
    if request.source.value == "PHONE" and request.phone:
        return request.phone, "phone"
    if request.source.value == "WECHAT" and request.wechat:
        return request.wechat, "wechat"
    if request.social_contact:
        contact_type = request.source.value.lower()
        return request.social_contact, contact_type if contact_type in {"facebook", "xiaohongshu"} else "other"
    if request.phone:
        return request.phone, "phone"
    if request.wechat:
        return request.wechat, "wechat"
    raise ValueError("Manual lead contact is required.")
