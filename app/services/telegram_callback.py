"""Token-based Telegram callback handling without approval business logic."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.approval_action_processor import (
    ApprovalActionProcessorError,
    process_approval_action,
)
from app.services.approval_action_service import ApprovalActionTokenError


INVALID_CALLBACK_DATA = "INVALID_CALLBACK_DATA"
SUPPORTED_CALLBACK_ACTIONS = frozenset({"APPROVE", "DECLINE"})


def handle_telegram_callback(
    callback_data: str,
    actor: str,
    db: Session,
) -> str:
    """Parse token callback data and delegate all state changes to the processor."""

    parsed = _parse_callback_data(callback_data)
    if parsed is None:
        return INVALID_CALLBACK_DATA

    _, token = parsed
    try:
        approval = process_approval_action(db, token, actor)
    except (ApprovalActionTokenError, ApprovalActionProcessorError) as exc:
        return exc.code

    if approval.status == "APPROVED":
        return "Approval approved successfully."
    if approval.status == "DECLINED":
        return "Approval declined successfully."
    return INVALID_CALLBACK_DATA


def _parse_callback_data(callback_data: str) -> tuple[str, str] | None:
    if not isinstance(callback_data, str):
        return None

    action, separator, token = callback_data.partition(":")
    if separator != ":" or action not in SUPPORTED_CALLBACK_ACTIONS:
        return None
    if not token or token.strip() != token or ":" in token:
        return None
    return action, token
