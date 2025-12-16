"""
Review Router - Content review agent
"""
import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import ReviewRequest, ReviewResponse
from app.services.gemini import GeminiService


router = APIRouter()
logger = structlog.get_logger()


@router.post("/review", response_model=ReviewResponse)
async def run_review(request: ReviewRequest):
    """
    Run the reviewer agent to critique content.
    
    Evaluates content quality and provides feedback
    with a score and approval status.
    """
    try:
        logger.info(
            "Review request",
            iteration=request.iteration,
            output_type=request.outputType.value,
            draft_length=len(request.draft)
        )
        
        service = GeminiService()
        feedback = await service.run_reviewer_agent(
            draft=request.draft,
            iteration=request.iteration,
            output_type=request.outputType,
            previous_scores=None,  # Individual endpoint doesn't track history
            previous_critique=None
        )
        
        logger.info(
            "Review completed",
            iteration=request.iteration,
            score=feedback.score,
            approved=feedback.approved
        )
        
        return ReviewResponse(feedback=feedback)
        
    except Exception as e:
        logger.error("Review failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}")
