from datetime import datetime
from zoneinfo import ZoneInfo


LA_TIMEZONE = ZoneInfo("America/Los_Angeles")


def parse_service_datetime(
    date_text: str | None,
    time_text: str | None,
) -> datetime | None:
    """
    Convert customer date/time text into Los Angeles datetime.
    """

    if not date_text or not time_text:
        return None


    try:
        # V1: 支持格式
        # 8月15日
        # 17:30

        month = int(
            date_text.replace("月", "-")
            .split("-")[0]
        )

        day = int(
            date_text.replace("月", "-")
            .replace("日", "")
            .split("-")[1]
        )


        hour, minute = map(
            int,
            time_text.split(":")
        )


        now = datetime.now(
            LA_TIMEZONE
        )


        return datetime(
            year=now.year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            tzinfo=LA_TIMEZONE,
        )


    except Exception:
        return None