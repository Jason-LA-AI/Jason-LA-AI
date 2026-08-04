"""Validation-only V2.1 quote request endpoint."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.quote_request import QuoteRequestCreate
from app.services.quote_estimate_lookup import (
    ESTIMATE_EXPIRED,
    ESTIMATE_NOT_AVAILABLE,
    ESTIMATE_NOT_FOUND,
    QuoteEstimateLookupError,
)
from app.services.quote_request_service import (
    QuoteRequestError,
    QuoteRequestProcessed,
    process_quote_request,
)


router = APIRouter()

ERROR_STATUS_CODES = {
    ESTIMATE_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ESTIMATE_EXPIRED: status.HTTP_410_GONE,
    ESTIMATE_NOT_AVAILABLE: status.HTTP_409_CONFLICT,
}

ERROR_MESSAGES = {
    "CONTACT_METHOD_REQUIRED": "Provide a phone number or email address.",
    "PHONE_REQUIRED_FOR_SMS": "A phone number is required for SMS contact.",
    "EMAIL_REQUIRED_FOR_EMAIL": "An email address is required for email contact.",
    ESTIMATE_NOT_FOUND: "The estimate was not found.",
    ESTIMATE_EXPIRED: "The estimate has expired.",
    ESTIMATE_NOT_AVAILABLE: "The estimate is no longer available.",
}


@router.post(
    "",
    response_model=QuoteRequestProcessed,
    status_code=status.HTTP_200_OK,
    summary="Validate an accepted quote estimate",
)
def create_quote_request(
    request: QuoteRequestCreate,
    db_session: Session = Depends(get_db_session),
) -> QuoteRequestProcessed | JSONResponse:
    """Process an accepted estimate into records awaiting Jason review."""

    try:
        return process_quote_request(db_session, request)
    except QuoteRequestError as exc:
        return _error_response(exc.code, status.HTTP_400_BAD_REQUEST)
    except QuoteEstimateLookupError as exc:
        return _error_response(
            exc.code,
            ERROR_STATUS_CODES.get(exc.code, status.HTTP_400_BAD_REQUEST),
        )


def _error_response(code: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": ERROR_MESSAGES.get(code, "Unable to accept this estimate."),
            }
        },
    )
