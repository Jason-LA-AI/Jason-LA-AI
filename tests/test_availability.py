from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.availability_checker import has_schedule_conflict


class FakeOrder:
    def __init__(self, pickup_at, status="CONFIRMED"):
        self.pickup_at = pickup_at
        self.status = status



def test_schedule_conflict():

    existing = [
        FakeOrder(
            datetime(
                2026,
                8,
                15,
                17,
                30,
                tzinfo=ZoneInfo("America/Los_Angeles"),
            )
        )
    ]


    result = has_schedule_conflict(
        datetime(
            2026,
            8,
            15,
            18,
            0,
            tzinfo=ZoneInfo("America/Los_Angeles"),
        ),
        existing,
    )


    assert result is True