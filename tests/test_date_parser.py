from app.services.date_parser import parse_service_datetime


def test_parse_service_datetime():

    result = parse_service_datetime(
        "8月15日",
        "17:30",
    )

    assert result is not None
    assert result.month == 8
    assert result.day == 15
    assert result.hour == 17
    assert result.minute == 30