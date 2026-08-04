"""Structured V2.1 quote estimate endpoint."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.quote_estimate import QuoteEstimateCreate, QuoteEstimateResponse
from app.services.quote_estimate_service import create_quote_estimate


router = APIRouter()


@router.post(
    "",
    response_model=QuoteEstimateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Quote estimate business rule error",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "QUOTE_ESTIMATE_ERROR",
                            "message": "Unable to create an estimate.",
                        }
                    }
                }
            },
        }
    },
    summary="Create a development quote estimate",
)
def create_quote_estimate_endpoint(
    request: QuoteEstimateCreate,
    db_session: Session = Depends(get_db_session),
) -> QuoteEstimateResponse | JSONResponse:
    """Persist and return a development estimate for structured trip details."""

    try:
        return create_quote_estimate(request, db_session)
    except ValueError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "QUOTE_ESTIMATE_ERROR",
                    "message": str(exc),
                }
            },
        )
