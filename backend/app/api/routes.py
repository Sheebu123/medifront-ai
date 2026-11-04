"""Top-level routes exposed by the backend API."""

from fastapi import APIRouter

from app.api.appointments import router as appointments_router
from app.api.auth import router as auth_router
from app.core.config import API_VERSION, APP_TITLE

router = APIRouter()
router.include_router(auth_router)
router.include_router(appointments_router)


@router.get("/", tags=["general"])
async def read_root() -> dict[str, str]:
    """Return a small welcome response for the API root."""
    return {
        "name": APP_TITLE,
        "version": API_VERSION,
        "message": "Welcome to the MediFront AI backend.",
    }


@router.get("/health", tags=["general"])
async def health_check() -> dict[str, str]:
    """Report that the API process is responding to requests."""
    return {"status": "healthy"}
