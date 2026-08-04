"""Top-level API router."""

from fastapi import APIRouter

from app.api.inquiries import router as inquiries_router
from app.api.chat import router as chat_router
from app.api.quote_estimates import router as quote_estimates_router
from app.api.quote_requests import router as quote_requests_router
from app.api.telegram import router as telegram_router


api_router = APIRouter()

api_router.include_router(
    inquiries_router,
    prefix="/inquiries",
    tags=["inquiries"],
)
api_router.include_router(
    chat_router,
    prefix="/chat"
)

api_router.include_router(
    quote_estimates_router,
    prefix="/quote-estimates",
    tags=["quote-estimates"],
)

api_router.include_router(
    quote_requests_router,
    prefix="/quote-requests",
    tags=["quote-requests"],
)

api_router.include_router(
    telegram_router,
    prefix="/telegram",
    tags=["telegram"],
)
