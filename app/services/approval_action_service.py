"""Secure creation and validation of approval action credentials."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval_action_token import ApprovalActionToken


TOKEN_NOT_FOUND = "TOKEN_NOT_FOUND"
TOKEN_EXPIRED = "TOKEN_EXPIRED"
TOKEN_ALREADY_USED = "TOKEN_ALREADY_USED"

TOKEN_LIFETIME = timedelta(minutes=15)
SUPPORTED_ACTIONS = frozenset({"APPROVE", "DECLINE"})


class ApprovalActionTokenError(Exception):
    """Business error raised when an approval action token is invalid."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def create_approval_action_token(
    db: Session,
    approval_id: UUID,
    action: str,
) -> str:
    """Persist only a token hash and return the plaintext credential once."""

    if action not in SUPPORTED_ACTIONS:
        raise ValueError("Approval action must be APPROVE or DECLINE.")

    plaintext_token = token_urlsafe(32)
    token_record = ApprovalActionToken(
        approval_id=approval_id,
        action=action,
        token_hash=_hash_token(plaintext_token),
        expires_at=datetime.now(timezone.utc) + TOKEN_LIFETIME,
        used_at=None,
        status="ACTIVE",
    )
    db.add(token_record)
    db.flush()
    return plaintext_token


def validate_approval_action_token(
    db: Session,
    token: str,
) -> ApprovalActionToken:
    """Return an active, unused, unexpired token record without consuming it."""

    token_record = db.scalar(
        select(ApprovalActionToken).where(
            ApprovalActionToken.token_hash == _hash_token(token)
        )
    )
    if token_record is None:
        raise ApprovalActionTokenError(TOKEN_NOT_FOUND)

    if token_record.used_at is not None or token_record.status == "USED":
        raise ApprovalActionTokenError(TOKEN_ALREADY_USED)

    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if token_record.status == "EXPIRED" or expires_at < datetime.now(timezone.utc):
        raise ApprovalActionTokenError(TOKEN_EXPIRED)

    if token_record.status != "ACTIVE":
        raise ApprovalActionTokenError(TOKEN_NOT_FOUND)

    return token_record


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
