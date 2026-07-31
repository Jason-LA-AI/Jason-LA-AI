from datetime import datetime, timedelta


BUFFER_BEFORE = timedelta(hours=1)
BUFFER_AFTER = timedelta(hours=2)


def has_schedule_conflict(
    requested_time: datetime,
    existing_orders: list,
) -> bool:
    """
    Check whether requested pickup time conflicts
    with existing confirmed orders.
    """

    requested_start = requested_time - BUFFER_BEFORE
    requested_end = requested_time + BUFFER_AFTER


    for order in existing_orders:

        if not order.pickup_at:
            continue


        if order.status == "CANCELLED":
            continue


        existing_start = order.pickup_at - BUFFER_BEFORE
        existing_end = order.pickup_at + BUFFER_AFTER


        if (
            requested_start <= existing_end
            and requested_end >= existing_start
        ):
            return True


    return False