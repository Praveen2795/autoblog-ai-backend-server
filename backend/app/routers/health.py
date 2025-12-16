"""
Health check endpoints.
"""
from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Returns service status and configuration state.
    """
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        gemini_configured=bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "")
    )


@router.get("/ready")
async def readiness_check():
    """
    Readiness check for Kubernetes/container orchestration.
    """
    # Check if Gemini API key is configured
    if not settings.GEMINI_API_KEY:
        return {"status": "not_ready", "reason": "GEMINI_API_KEY not configured"}
    
    return {"status": "ready"}
