"""
Refine Router - Content refinement agent
"""
import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import RefineRequest, RefineResponse
from app.services.gemini import GeminiService


router = APIRouter()
logger = structlog.get_logger()


@router.post("/refine", response_model=RefineResponse)
async def run_refine(request: RefineRequest):
    """
    Run the refiner agent to improve content based on feedback.
    
    Takes the draft and reviewer feedback to produce
    an improved version of the content.
    """
    try:
        logger.info(
            "Refine request",
            output_type=request.outputType.value,
            draft_length=len(request.draft),
            feedback_length=len(request.feedback)
        )
        
        service = GeminiService()
        refined = await service.run_refiner_agent(
            draft=request.draft,
            feedback=request.feedback,
            output_type=request.outputType
        )
        
        logger.info(
            "Refine completed",
            output_type=request.outputType.value,
            refined_length=len(refined)
        )
        
        return RefineResponse(refinedDraft=refined)
        
    except Exception as e:
        logger.error("Refine failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")
