"""Generate customer-facing replies for Jason."""

from app.schemas.inquiry_analysis import ExtractedInquiryInformation


REPLY_KNOWLEDGE_FILES = (
    "brand_profile.md",
    "customer_reply_templates.md",
)


def generate_initial_reply(
    customer_name: str | None,
    extracted_information: ExtractedInquiryInformation,
    missing_information: list[str],
) -> str:
    """
    Generate customer-facing reply.

    Shows information already provided by customer,
    and only asks for missing details.
    """

    name = customer_name or "您好"


    summary = _build_summary(
        extracted_information
    )


    if missing_information:

        missing_text = _format_missing_information(
            missing_information
        )


        return f"""
{name}，您好，我是 Jason。谢谢您的咨询。

我已经收到您的行程信息：

{summary}


为了进一步确认行程，还需要：

{missing_text}


收到完整资料后，我会确认档期和费用。

谢谢。
""".strip()


    return f"""
{name}，您好，我是 Jason。

我已经收到您的行程信息：

{summary}


我正在确认档期和费用，
确认后回复您。

谢谢。
""".strip()



def _build_summary(
    extracted: ExtractedInquiryInformation,
) -> str:

    lines = []


    if extracted.date:
        lines.append(
            f"📅 日期：{extracted.date}"
        )


    if extracted.pickup_time:
        lines.append(
            f"⏰ 时间：{extracted.pickup_time}"
        )


    if extracted.airport:
        lines.append(
            f"✈ 机场：{extracted.airport}"
        )


    if extracted.destination:
        lines.append(
            f"📍 目的地：{extracted.destination}"
        )


    if extracted.passengers:
        lines.append(
            f"👥 人数：{extracted.passengers}"
        )


    if extracted.luggage:
        lines.append(
            f"🧳 行李：{extracted.luggage}"
        )


    if extracted.flight_information:
        lines.append(
            f"✈ 航班：{extracted.flight_information}"
        )


    return "\n".join(lines)



def _format_missing_information(
    missing_information: list[str],
) -> str:

    mapping = {

        "date": "• 用车日期",

        "pickup_time": "• 接送时间",

        "pickup_location": "• 上车地点",

        "destination": "• 目的地",

        "airport": "• 机场名称",

        "flight_information":
            "• 航空公司和航班号",

        "passenger_count":
            "• 乘客人数",

        "luggage_details":
            "• 行李数量和尺寸",

        "child_seat_requirements":
            "• 儿童座椅需求",

        "special_requests":
            "• 其他特殊需求",
    }


    lines = []


    for item in missing_information:

        if item in mapping:

            lines.append(
                mapping[item]
            )


    return "\n".join(lines)