from sqlalchemy.orm import Session

from app.models.order import Order
from app.services.availability_checker import has_schedule_conflict


ACTIVE_STATUS = [
    "CONFIRMED",
    "WAITING_FOR_JASON_APPROVAL",
    "WAITING_FOR_INFORMATION",
]


def check_order_availability(
    db_session: Session,
    pickup_at,
) -> bool:

    existing_orders = (
        db_session.query(Order)
        .filter(
            Order.status.in_(ACTIVE_STATUS)
        )
        .all()
    )

    result = has_schedule_conflict(
    pickup_at,
    existing_orders,
)

    print("DEBUG existing orders:", len(existing_orders))
    print("DEBUG requested:", pickup_at)
    print("DEBUG conflict:", result)

    return not result