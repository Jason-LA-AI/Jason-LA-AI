"""Top-level API router.

Feature routers will be registered here as Phase 1 is implemented.
"""

from fastapi import APIRouter

from app.api.inquiries import router as inquiries_router


api_router = APIRouter()
api_router.include_router(inquiries_router, prefix="/inquiries", tags=["inquiries"])
